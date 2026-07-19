process GATK4_GENOTYPEGVCFS {
    tag "$meta.id"
    label 'process_medium'

    conda 'bioconda::gatk4=4.5.0.0'
    container 'biocontainers/gatk4:4.5.0.0--py36hdfd78af_0'

    input:
    tuple val(meta), path(gvcf), path(tbi)
    path fasta
    path fai
    path dict

    output:
    tuple val(meta), path('*.vcf.gz'), path('*.vcf.gz.tbi'), emit: vcf
    path 'versions.yml',                                     emit: versions

    script:
    def prefix    = task.ext.prefix ?: "${meta.id}"
    def avail_mem = (task.memory ? (task.memory.giga * 0.8).intValue() : 2)
    """
    gatk --java-options "-Xmx${avail_mem}g" GenotypeGVCFs \\
        --variant ${gvcf} \\
        --reference ${fasta} \\
        --output ${prefix}.vcf.gz

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        gatk4: \$( gatk --version 2>&1 | grep -oP 'GATK.*v\\K[0-9.]+' | head -1 )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    echo | gzip > ${prefix}.vcf.gz
    touch ${prefix}.vcf.gz.tbi
    echo '"${task.process}": {gatk4: stub}' > versions.yml
    """
}
