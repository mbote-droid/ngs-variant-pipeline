process MINIMAP2_ALIGN {
    tag "$meta.id"
    label 'process_high'

    conda 'bioconda::minimap2=2.28 bioconda::samtools=1.20'
    // Multi-tool step (minimap2 | samtools) needs one image with both: the
    // pinned nf-core mulled biocontainer. versions.yml reports runtime versions.
    container 'biocontainers/mulled-v2-66534bcbb7031a148b13e2ad42583020b9cd25c4:3161f532a5ea6f1dec9be5667c7efc0d7556a50d-0'

    input:
    tuple val(meta), path(reads)
    path fasta
    val  preset            // minimap2 preset: 'map-ont' (Nanopore) or 'map-hifi' (PacBio HiFi)

    output:
    tuple val(meta), path('*.sorted.bam'), path('*.sorted.bam.bai'), emit: bam
    path 'versions.yml',                                             emit: versions

    // Long-read alignment (M9). Long reads are single-file (no R1/R2); the read
    // group SM is the sample id so downstream tools tag calls correctly.
    script:
    def prefix    = task.ext.prefix ?: "${meta.id}"
    def rg        = "@RG\\tID:${meta.id}\\tSM:${meta.id}\\tPL:${preset == 'map-hifi' ? 'PACBIO' : 'ONT'}\\tLB:${meta.id}"
    def readList  = (reads instanceof List ? reads : [reads]).join(' ')
    """
    minimap2 -ax ${preset} -t ${task.cpus} -R "${rg}" --MD ${fasta} ${readList} \\
        | samtools sort -@ ${task.cpus} -o ${prefix}.sorted.bam -
    samtools index ${prefix}.sorted.bam

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        minimap2: \$( minimap2 --version )
        samtools: \$( samtools --version | head -1 | sed 's/samtools //' )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}.sorted.bam ${prefix}.sorted.bam.bai
    echo '"${task.process}": {minimap2: stub, samtools: stub}' > versions.yml
    """
}
