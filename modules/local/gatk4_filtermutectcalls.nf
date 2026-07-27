process GATK4_FILTERMUTECTCALLS {
    tag "$meta.id"
    label 'process_medium'

    conda 'bioconda::gatk4=4.5.0.0'
    container 'biocontainers/gatk4:4.5.0.0--py36hdfd78af_0'

    input:
    tuple val(meta), path(vcf), path(tbi), path(stats), path(orientation_model)
    path fasta
    path fai
    path dict

    output:
    tuple val(meta), path('*.filtered.vcf.gz'), path('*.filtered.vcf.gz.tbi'), emit: vcf
    path 'versions.yml',                                                       emit: versions

    // Apply the somatic filters (M7): labels calls PASS or with a filter reason
    // (weak evidence, germline, orientation bias, …) using Mutect2's stats and
    // the read-orientation priors.
    script:
    def prefix    = task.ext.prefix ?: "${meta.id}"
    def avail_mem = (task.memory ? (task.memory.giga * 0.8).intValue() : 3)
    """
    gatk --java-options "-Xmx${avail_mem}g" FilterMutectCalls \\
        --reference ${fasta} \\
        --variant ${vcf} \\
        --stats ${stats} \\
        --ob-priors ${orientation_model} \\
        --output ${prefix}.filtered.vcf.gz

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
