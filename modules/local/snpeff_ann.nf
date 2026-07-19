process SNPEFF_ANN {
    tag "$meta.id"
    label 'process_medium'

    conda 'bioconda::snpeff=5.2 bioconda::tabix=1.11'
    container 'biocontainers/snpeff:5.2--hdfd78af_0'

    input:
    tuple val(meta), path(vcf), path(tbi)
    tuple path(snpeff_data), path(config)
    val  db

    output:
    tuple val(meta), path('*.snpeff.vcf.gz'), path('*.snpeff.vcf.gz.tbi'), emit: vcf
    tuple val(meta), path('*.snpeff.csv'),                                 emit: report
    path 'versions.yml',                                                   emit: versions

    script:
    def prefix    = task.ext.prefix ?: "${meta.id}"
    def avail_mem = (task.memory ? (task.memory.giga * 0.8).intValue() : 2)
    """
    snpEff ann -Xmx${avail_mem}g \\
        -dataDir \$PWD/${snpeff_data} -c ${config} \\
        -csvStats ${prefix}.snpeff.csv \\
        ${db} ${vcf} > ${prefix}.snpeff.vcf

    bgzip ${prefix}.snpeff.vcf
    tabix -p vcf ${prefix}.snpeff.vcf.gz

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        snpeff: \$( snpEff -version 2>&1 | sed 's/SnpEff\\s*//' | head -1 )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    echo | gzip > ${prefix}.snpeff.vcf.gz
    touch ${prefix}.snpeff.vcf.gz.tbi ${prefix}.snpeff.csv
    echo '"${task.process}": {snpeff: stub}' > versions.yml
    """
}
