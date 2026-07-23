process GATK4_LEARNREADORIENTATIONMODEL {
    tag "$meta.id"
    label 'process_medium'

    conda 'bioconda::gatk4=4.5.0.0'
    container 'biocontainers/gatk4:4.5.0.0--py36hdfd78af_0'

    input:
    tuple val(meta), path(f1r2)

    output:
    tuple val(meta), path('*.read-orientation-model.tar.gz'), emit: model
    path 'versions.yml',                                      emit: versions

    // Model of FFPE/oxidation read-orientation artefacts (M7); its priors let
    // FilterMutectCalls flag orientation-biased false positives.
    script:
    def prefix    = task.ext.prefix ?: "${meta.id}"
    def avail_mem = (task.memory ? (task.memory.giga * 0.8).intValue() : 3)
    """
    gatk --java-options "-Xmx${avail_mem}g" LearnReadOrientationModel \\
        --input ${f1r2} \\
        --output ${prefix}.read-orientation-model.tar.gz

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        gatk4: \$( gatk --version 2>&1 | grep -oP 'GATK.*v\\K[0-9.]+' | head -1 )
    END_VERSIONS
    """

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    """
    touch ${prefix}.read-orientation-model.tar.gz
    echo '"${task.process}": {gatk4: stub}' > versions.yml
    """
}
