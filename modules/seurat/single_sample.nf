process SEURAT_SINGLE_SAMPLE {
    publishDir "$params.output_dir", mode: 'copy', pattern: 'seurat_obj.rds'
    publishDir "$params.output_dir", mode: 'copy', pattern: 'umap_clusters.png'
    publishDir "$params.output_dir/intermediate_R", mode: 'copy', pattern: 'clusters.rds', enabled: params.save_intermediates
    label "r"
    label "medium_cpu"
    label "medium_mem"
    label "medium"

    input:
    path(se)

    output:
    path ('clusters.rds'), emit: clusters
    path ('seurat_obj.rds'), emit: seurat_obj
    path ('umap_clusters.png'), emit: umap_plot
    path "versions.yml", topic: 'versions'

    script:
    """
    #!/usr/bin/env Rscript
    library(SummarizedExperiment)
    library(IRanges)
    library(Seurat)

    se     <- readRDS("$se")
    counts <- assays(se)\$counts
    # Seurat v5 LayerData<- fails on non-standard sparse formats; coerce to dgCMatrix
    counts <- as(counts, "CsparseMatrix")
    counts <- as(counts, "dgCMatrix")
    # drop empty rows/cols that trip up CreateSeuratObject
    counts <- counts[Matrix::rowSums(counts) > 0, , drop = FALSE]
    counts <- counts[, Matrix::colSums(counts) > 0, drop = FALSE]
    cat("counts dim:", dim(counts), " totals:", sum(counts), "\n")
    if (ncol(counts) == 0 || nrow(counts) == 0)
        stop("Empty counts matrix - no cells or genes after filtering")
    if (ncol(counts) < 3) {
        # too few cells to cluster (e.g. small test data); save placeholders so the
        # pipeline continues (BAMBU_EM falls back to per-cell quantification)
        warning("Too few cells for clustering (", ncol(counts), ") - skipping Seurat clustering")
        saveRDS(NULL, "seurat_obj.rds")
        saveRDS(NULL, "clusters.rds")
        saveRDS(NULL, "cell_mix.rds")
        # placeholder so the declared umap_clusters.png output exists
        png("umap_clusters.png", width = 800, height = 600, res = 150)
        plot.new(); text(0.5, 0.5, paste0("Too few cells for clustering (", ncol(counts), ")"))
        dev.off()
        writeLines(c(
            '"${task.process}":',
            paste0('    R: ',                   R.Version()\$version.string),
            paste0('    seurat: ',              as.character(packageVersion("Seurat")))
        ), "versions.yml")
        quit(save = "no", status = 0)
    }
    # Retry with dense matrix if sparse path fails (Seurat v5 bug)
    cellMix <- tryCatch(
        CreateSeuratObject(counts = counts, project = "cellMix", min.cells = 1),
        error = function(e) CreateSeuratObject(counts = as.matrix(counts), project = "cellMix", min.cells = 1)
    )
    dim    <- $params.seurat_dim_single

    # Single sample scRNA-seq clustering adapted from https://satijalab.org/seurat/articles/pbmc3k_tutorial.html
    cellMix <- NormalizeData(cellMix, normalization.method = "LogNormalize", scale.factor = 10000)
    cellMix <- FindVariableFeatures(cellMix, selection.method = "vst", nfeatures = 2500)
    cellMix <- ScaleData(cellMix)
    npcs    <- ifelse(ncol(counts) > 50, 50, ncol(counts) - 1)
    cellMix <- RunPCA(cellMix, features = VariableFeatures(object = cellMix), npcs = npcs)
    dim     <- ifelse(dim >= dim(cellMix@reductions\$pca)[2], dim(cellMix@reductions\$pca)[2], dim)
    cellMix <- FindNeighbors(cellMix, dims = 1:dim)
    cellMix <- FindClusters(cellMix, resolution = $params.resolution)
    cellMix <- RunUMAP(cellMix, dims = 1:dim)
    saveRDS(cellMix, "seurat_obj.rds")

    # Plot UMAP colored by cluster (clustering is on bin50 cells for stereoseq)
    png("umap_clusters.png", width = 1200, height = 1000, res = 150)
    print(DimPlot(cellMix, reduction = "umap", label = TRUE) + ggtitle("UMAP - clusters"))
    dev.off()

    x <- setNames(names(cellMix@active.ident), cellMix@active.ident)
    clusters <- list(splitAsList(unname(x), paste0("cluster", names(x))))
    saveRDS(clusters, "clusters.rds")

    saveRDS(cellMix, "cell_mix.rds")
    writeLines(c(
        '"${task.process}":',
        paste0('    R: ',                   R.Version()\$version.string),
        paste0('    seurat: ',              as.character(packageVersion("Seurat"))),
        paste0('    IRanges: ',             as.character(packageVersion("IRanges"))),
        paste0('    SummarizedExperiment: ', as.character(packageVersion("SummarizedExperiment")))
    ), "versions.yml")
    """
}
