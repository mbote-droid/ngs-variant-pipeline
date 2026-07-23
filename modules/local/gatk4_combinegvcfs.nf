process GATK4_COMBINEGVCFS {
    tag "$meta.id"
    label 'process_medium'

    conda 'bioconda::gatk4=4.5.0.0'
    container 'biocontainers/gatk4:4.5.0.0--py36hdfd78af_0'

    input:
    tuple val(meta), path(gvcfs), path(tbis)
    path fasta
    path fai
    path dict

    output:
    tuple val(meta), path('*.combined.g.vcf.gz'), path('*.combined.g.vcf.gz.tbi'), emit: gvcf
    path 'versions.yml',                                                           emit: versions

    // Combine per-sample GVCFs into one multi-sample GVCF for cohort joint
    // genotyping (H5). GenomicsDBImport is the alternative at very large N.
    script:
    def prefix     = task.ext.prefix ?: "${meta.id}"
    def avail_mem  = (task.memory ? (task.memory.giga * 0.8).intValue() : 3)
    def variant_args = (gvcfs instanceof List ? gvcfs : [gvcfs]).collect { "--variant ${it}" }.join(' ')
    """
    gatk --java-options "-Xmx${avail_mem}g" CombineGVCFs \\
        --reference ${fasta} \\
        ${variant_args} \\
        --output ${prefix}.combined.g.vcf.gz

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        gatk4: \$( gatk --version 2>&1 | grep -oP 'GATK.*v\\K[0-9.]+' | head -1 )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    echo | gzip > ${prefix}.combined.g.vcf.gz
    touch ${prefix}.combined.g.vcf.gz.tbi
    echo '"${task.process}": {gatk4: stub}' > versions.yml
    """
}
