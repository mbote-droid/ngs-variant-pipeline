process SAMTOOLS_FLAGSTAT {
    tag "$meta.id"
    label 'process_single'

    conda 'bioconda::samtools=1.19.2'
    container 'biocontainers/samtools:1.19.2--h50ea8bc_0'

    input:
    tuple val(meta), path(bam), path(bai)

    output:
    tuple val(meta), path('*.flagstat'), emit: flagstat
    path 'versions.yml',                 emit: versions

    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    samtools flagstat ${bam} > ${prefix}.flagstat

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        samtools: \$( samtools --version | head -1 | sed 's/samtools //' )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}.flagstat
    echo '"${task.process}": {samtools: stub}' > versions.yml
    """
}
