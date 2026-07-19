process GATK4_MARKDUPLICATES {
    tag "$meta.id"
    label 'process_medium'

    conda 'bioconda::gatk4=4.5.0.0'
    container 'biocontainers/gatk4:4.5.0.0--py36hdfd78af_0'

    input:
    tuple val(meta), path(bam), path(bai)

    output:
    tuple val(meta), path('*.md.bam'), path('*.md.bai'), emit: bam
    tuple val(meta), path('*.metrics.txt'),              emit: metrics
    path 'versions.yml',                                 emit: versions

    script:
    def prefix    = task.ext.prefix ?: "${meta.id}"
    def avail_mem = (task.memory ? (task.memory.giga * 0.8).intValue() : 2)
    """
    gatk --java-options "-Xmx${avail_mem}g" MarkDuplicates \\
        --INPUT ${bam} \\
        --OUTPUT ${prefix}.md.bam \\
        --METRICS_FILE ${prefix}.metrics.txt \\
        --CREATE_INDEX true

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        gatk4: \$( gatk --version 2>&1 | grep -oP 'GATK.*v\\K[0-9.]+' | head -1 )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}.md.bam ${prefix}.md.bai ${prefix}.metrics.txt
    echo '"${task.process}": {gatk4: stub}' > versions.yml
    """
}
