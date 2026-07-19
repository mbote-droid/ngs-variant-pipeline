process GATK4_HAPLOTYPECALLER {
    tag "$meta.id"
    label 'process_high'

    conda 'bioconda::gatk4=4.5.0.0'
    container 'biocontainers/gatk4:4.5.0.0--py36hdfd78af_0'

    input:
    tuple val(meta), path(bam), path(bai)
    path fasta
    path fai
    path dict

    output:
    tuple val(meta), path('*.g.vcf.gz'), path('*.g.vcf.gz.tbi'), emit: gvcf
    path 'versions.yml',                                         emit: versions

    script:
    def prefix    = task.ext.prefix ?: "${meta.id}"
    def avail_mem = (task.memory ? (task.memory.giga * 0.8).intValue() : 2)
    """
    gatk --java-options "-Xmx${avail_mem}g" HaplotypeCaller \\
        --input ${bam} \\
        --reference ${fasta} \\
        --output ${prefix}.g.vcf.gz \\
        --emit-ref-confidence GVCF

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        gatk4: \$( gatk --version 2>&1 | grep -oP 'GATK.*v\\K[0-9.]+' | head -1 )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    echo | gzip > ${prefix}.g.vcf.gz
    touch ${prefix}.g.vcf.gz.tbi
    echo '"${task.process}": {gatk4: stub}' > versions.yml
    """
}
