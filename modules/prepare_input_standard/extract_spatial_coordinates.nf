process EXTRACT_10X_SPATIAL_COORDINATES {
    label "spaceranger"
    executor 'local'

    input:
    val(chemistry)
    path(barcode_coordinate_config)

    output:
    tuple val(chemistry), path("${chemistry}_spatial_coordinates.txt"), emit: spatial_coordinates

    script:
    if (chemistry == 'stereoseq') {
        """
        # Placeholder: spatial coordinates are extracted from the ST_BarcodeMap
        # output during preprocessing. For now, write an empty file (header only);
        # actual coords will be generated from the BAM in a future step.
        echo 'barcode\\tx_coordinate\\ty_coordinate' > ./${chemistry}_spatial_coordinates.txt
        """
    } else {
        """
        # extract spatial coordinate file path from config csv
        IFS=',' read -r _ _ sc_filename < <(awk -F',' -v chem=$chemistry '\$1 == chem' $barcode_coordinate_config)

        cp $params.cellranger_dir/\$sc_filename ./${chemistry}_spatial_coordinates.txt
        sed -i '1ibarcode\\tx_coordinate\\ty_coordinate' ./${chemistry}_spatial_coordinates.txt
        """
    }
}
