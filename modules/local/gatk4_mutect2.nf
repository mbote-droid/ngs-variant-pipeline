process GATK4_MUTECT2 {
    tag "$meta.id"
    label 'process_high'

    conda 'bioconda::gatk4=4.5.0.0'
    container 'biocontainers/gatk4:4.5.0.0--py36hdfd78af_0'

    input:
    tuple val(meta), path(tumor_bam), path(tumor_bai), path(normal_bam), path(normal_bai)
    path fasta
    path fai
    path dict
    path pon           // panel of normals VCF, or [] if none
    path pon_tbi       // its .tbi,               or []
    path germline      // germline-resource VCF,  or []
    path germline_tbi  // its .tbi,               or []

    output:
    tuple val(meta), path('*.unfiltered.vcf.gz'), path('*.unfiltered.vcf.gz.tbi'), emit: vcf
    tuple val(meta), path('*.unfiltered.vcf.gz.stats'),                            emit: stats
    tuple val(meta), path('*.f1r2.tar.gz'),                                        emit: f1r2
    path 'versions.yml',                                                           emit: versions

    // Somatic short-variant calling in tumor/normal mode (M7). The normal sample
    // name (-normal) is the normal BAM's @RG SM, which the aligner set to the
    // normal sample id (meta.normal_id). Emits the f1r2 counts for the read
    // orientation model used by FilterMutectCalls.
    script:
    def prefix    = task.ext.prefix ?: "${meta.id}"
    def avail_mem = (task.memory ? (task.memory.giga * 0.8).intValue() : 4)
    def pon_arg   = pon      ? "--panel-of-normals ${pon}"     : ''
    def germ_arg  = germline ? "--germline-resource ${germline}" : ''
    """
    gatk --java-options "-Xmx${avail_mem}g" Mutect2 \\
        --reference ${fasta} \\
        --input ${tumor_bam} \\
        --input ${normal_bam} \\
        --normal-sample ${meta.normal_id} \\
        ${pon_arg} ${germ_arg} \\
        --f1r2-tar-gz ${prefix}.f1r2.tar.gz \\
        --output ${prefix}.unfiltered.vcf.gz

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        gatk4: \$( gatk --version 2>&1 | grep -oP 'GATK.*v\\K[0-9.]+' | head -1 )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    echo | gzip > ${prefix}.unfiltered.vcf.gz
    touch ${prefix}.unfiltered.vcf.gz.tbi ${prefix}.unfiltered.vcf.gz.stats
    touch ${prefix}.f1r2.tar.gz
    echo '"${task.process}": {gatk4: stub}' > versions.yml
    """
}
