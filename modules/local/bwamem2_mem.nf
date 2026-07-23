process BWAMEM2_MEM {
    tag "$meta.id"
    label 'process_high'

    conda 'bioconda::bwa-mem2=2.2.1 bioconda::samtools=1.19.2'
    // Multi-tool step (bwa-mem2 | samtools) needs a single image carrying both
    // tools: a pinned mulled biocontainer (bwa-mem2 2.2.1 + samtools). The image
    // bundles samtools 1.16.1; only sort/index are used here, so it is output-
    // equivalent to the conda pin (1.19.2). versions.yml reports the real runtime
    // versions. A version-matched image can be regenerated with `wave` (see
    // docs/CONTAINERS.md) on a Docker-capable host if exact parity is required.
    container 'biocontainers/mulled-v2-e5d375990341c5aef3c9aff74f96f66f65375ef6:2cdf6bf1e92acbeb9b2834b1c58b6a682df32abb-0'

    input:
    tuple val(meta), path(reads)
    path index   // bwamem2 index directory
    path fasta

    output:
    tuple val(meta), path('*.sorted.bam'), path('*.sorted.bam.bai'), emit: bam
    path 'versions.yml',                                             emit: versions

    script:
    def prefix    = task.ext.prefix ?: "${meta.id}"
    def rg        = "@RG\\tID:${meta.id}\\tSM:${meta.id}\\tPL:ILLUMINA\\tLB:${meta.id}"
    def reads_cmd = meta.single_end ? "${reads}" : "${reads[0]} ${reads[1]}"
    """
    INDEX=\$( find -L ./ -name "*.bwt.2bit.64" | sed 's/\\.bwt\\.2bit\\.64\$//' )
    bwa-mem2 mem -t ${task.cpus} -R "${rg}" \$INDEX ${reads_cmd} \\
        | samtools sort -@ ${task.cpus} -o ${prefix}.sorted.bam -
    samtools index ${prefix}.sorted.bam

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bwa-mem2: \$( bwa-mem2 version 2>&1 | head -1 )
        samtools: \$( samtools --version | head -1 | sed 's/samtools //' )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}.sorted.bam ${prefix}.sorted.bam.bai
    echo '"${task.process}": {bwa-mem2: stub, samtools: stub}' > versions.yml
    """
}
