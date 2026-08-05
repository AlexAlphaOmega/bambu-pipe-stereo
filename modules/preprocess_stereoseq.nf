process PREPROCESS_STEREOSEQ {
    label "preprocess"
    label "medium_cpu"
    label "high_mem"
    label "long"

    publishDir "$params.output_dir/intermediate_fastq",
        mode: 'symlink',
        pattern: '*.fastq.gz',
        enabled: params.save_intermediates

    input:
    tuple val(sample), path(fastq), val(meta)
    path(flank_seq_config)

    output:
    tuple val(sample), path("${sample}_preprocessed_reads.fastq.gz"), val(meta), emit: fastq
    path "versions.yml", topic: 'versions'

    script:
    def bs = params.stereoseq_binsize ?: "50"
    """
    set -euo pipefail

    #=======================================================================================================
    # Helper functions
    #=======================================================================================================
    decompress() {
        if [[ $fastq == *.gz ]]; then
            pigz -p $task.cpus -d -c $fastq
        else
            cat $fastq
        fi
    }

    save_intermediate() {
        local out_file=\$1
        if [[ $params.save_intermediates == "true" ]]; then
            tee >(pigz -p $task.cpus -c > \$out_file)
        else
            cat
        fi
    }

    chopper_cmd() {
        if [[ $params.qscore_filtering == "true" ]]; then
            chopper -q $params.qfilter_threshold -t $task.cpus
        else
            cat
        fi
    }

    #=======================================================================================================
    # Step 1: Quality filtering (Chopper)
    #=======================================================================================================
    decompress | chopper_cmd | save_intermediate "${sample}_intermediate_qfilter.fastq.gz" > ${sample}_chopper_out.fastq

    #=======================================================================================================
    # Step 2: Flexiplex barcode/UMI extraction (no whitelist)
    #=======================================================================================================
    IFS=',' read -r _ left_flank barcode umi right_flank < <(awk -F',' -v chem=stereoseq '\$1 == chem' $flank_seq_config)
    flank_seq="-x \$left_flank -b \$barcode -u \$umi -x \$right_flank"

    flexiplex -p $task.cpus \$flank_seq -f $params.flexiplex_f_3prime -e $params.flexiplex_e \
        ${sample}_chopper_out.fastq > ${sample}_flexiplex_out.fastq

    rm ${sample}_chopper_out.fastq

    #=======================================================================================================
    # Step 3: Split Flexiplex output -> read1 (CID+MID) + read2 (cDNA)
    #=======================================================================================================
    python3 $projectDir/bin/split_stereoseq_barcode.py \
        "${sample}_read1.fq" "${sample}_read2.fq" < ${sample}_flexiplex_out.fastq

    rm ${sample}_flexiplex_out.fastq

    #=======================================================================================================
    # Step 4: ST_BarcodeMap (CID -> spatial x_y)
    #=======================================================================================================
    # Scope ST_BarcodeMap's LD_LIBRARY_PATH to this command only
    _orig_ld=\${LD_LIBRARY_PATH:-}
    if [ -n "${params.stereoseq_ld_library_path}" ]; then
        export LD_LIBRARY_PATH=${params.stereoseq_ld_library_path}:\$_orig_ld
    fi

    ${params.stereoseq_barcode_map} --in ${params.stereoseq_mask} \
        --in1 ${sample}_read1.fq --in2 ${sample}_read2.fq \
        --out ${sample}_mapped_r1.fq.gz --out2 ${sample}_mapped_r2.fq.gz \
        --PEout --mismatch 1 -w ${task.cpus}

    export LD_LIBRARY_PATH=\$_orig_ld

    rm -f ${sample}_read1.fq ${sample}_read2.fq

    #=======================================================================================================
    # Step 5: Bin to target binsize + rewrite read name to bambu-pipe format
    #=======================================================================================================
    python3 $projectDir/bin/bin_stereoseq_barcode.py ${sample}_mapped_r2.fq.gz ${bs} \
        | pigz -p $task.cpus -c > ${sample}_preprocessed_reads.fastq.gz

    rm -f ${sample}_mapped_r1.fq.gz ${sample}_mapped_r2.fq.gz

    #=======================================================================================================
    # Version info
    #=======================================================================================================
    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$(python3 --version 2>&1)
        chopper: \$(chopper --version 2>&1 | head -1)
        flexiplex: \$(flexiplex --version 2>&1 | head -1)
    END_VERSIONS
    """
}