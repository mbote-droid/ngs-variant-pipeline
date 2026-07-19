process GATK4_VARIANTFILTRATION {
    tag "$meta.id"
    label 'process_medium'

    conda 'bioconda::gatk4=4.5.0.0'
    container 'biocontainers/gatk4:4.5.0.0--py36hdfd78af_0'

    input:
    tuple val(meta), path(vcf), path(tbi)
    path fasta
    path fai
    path dict

    output:
    tuple val(meta), path('*.filtered.vcf.gz'), path('*.filtered.vcf.gz.tbi'), emit: vcf
    path 'versions.yml',                                                       emit: versions

    script:
    def prefix    = task.ext.prefix ?: "${meta.id}"
    def avail_mem = (task.memory ? (task.memory.giga * 0.8).intValue() : 2)
    // GATK best-practice germline hard filters. VariantFiltration LABELS
    // failing records (it does not drop them), so nothing is silently lost.
    """
    gatk --java-options "-Xmx${avail_mem}g" VariantFiltration \\
        --reference ${fasta} \\
        --variant ${vcf} \\
        --output ${prefix}.filtered.vcf.gz \\
        --filter-name "QD2"        --filter-expression "QD < 2.0" \\
        --filter-name "FS60"       --filter-expression "FS > 60.0" \\
        --filter-name "MQ40"       --filter-expression "MQ < 40.0" \\
        --filter-name "MQRankSum"  --filter-expression "MQRankSum < -12.5" \\
        --filter-name "ReadPosRankSum" --filter-expression "ReadPosRankSum < -8.0" \\
        --filter-name "SOR3"       --filter-expression "SOR > 3.0"

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        gatk4: \$( gatk --version 2>&1 | grep -oP 'GATK.*v\\K[0-9.]+' | head -1 )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    echo | gzip > ${prefix}.filtered.vcf.gz
    touch ${prefix}.filtered.vcf.gz.tbi
    echo '"${task.process}": {gatk4: stub}' > versions.yml
    """
}
