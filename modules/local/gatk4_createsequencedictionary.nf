process GATK4_CREATESEQUENCEDICTIONARY {
    tag "$fasta"
    label 'process_medium'

    conda 'bioconda::gatk4=4.5.0.0'
    container 'biocontainers/gatk4:4.5.0.0--py36hdfd78af_0'

    input:
    path fasta

    output:
    path '*.dict',       emit: dict
    path 'versions.yml', emit: versions

    script:
    def avail_mem = (task.memory ? (task.memory.giga * 0.8).intValue() : 2)
    """
    gatk --java-options "-Xmx${avail_mem}g" CreateSequenceDictionary \\
        --REFERENCE ${fasta} \\
        --OUTPUT ${fasta.baseName}.dict

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        gatk4: \$( gatk --version 2>&1 | grep -oP 'GATK.*v\\K[0-9.]+' | head -1 )
    END_VERSIONS
    """

    stub:
    """
    touch ${fasta.baseName}.dict
    echo '"${task.process}": {gatk4: stub}' > versions.yml
    """
}
