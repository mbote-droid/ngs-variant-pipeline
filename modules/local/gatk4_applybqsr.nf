process GATK4_APPLYBQSR {
    tag "$meta.id"
    label 'process_medium'

    conda 'bioconda::gatk4=4.5.0.0'
    container 'biocontainers/gatk4:4.5.0.0--py36hdfd78af_0'

    input:
    tuple val(meta), path(bam), path(bai), path(table)
    path fasta
    path fai
    path dict

    output:
    tuple val(meta), path('*.recal.bam'), path('*.recal.bai'), emit: bam
    path 'versions.yml',                                       emit: versions

    script:
    def prefix    = task.ext.prefix ?: "${meta.id}"
    def avail_mem = (task.memory ? (task.memory.giga * 0.8).intValue() : 2)
    """
    gatk --java-options "-Xmx${avail_mem}g" ApplyBQSR \\
        --input ${bam} \\
        --reference ${fasta} \\
        --bqsr-recal-file ${table} \\
        --output ${prefix}.recal.bam \\
        --create-output-bam-index true

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        gatk4: \$( gatk --version 2>&1 | grep -oP 'GATK.*v\\K[0-9.]+' | head -1 )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}.recal.bam ${prefix}.recal.bai
    echo '"${task.process}": {gatk4: stub}' > versions.yml
    """
}
