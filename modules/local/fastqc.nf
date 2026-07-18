process FASTQC {
    tag "$meta.id"
    label 'process_medium'

    conda 'bioconda::fastqc=0.12.1'
    container 'biocontainers/fastqc:0.12.1--hdfd78af_0'

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path('*.html'), emit: html
    tuple val(meta), path('*.zip'),  emit: zip
    path 'versions.yml',             emit: versions

    script:
    """
    fastqc --threads ${task.cpus} ${reads}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        fastqc: \$( fastqc --version | sed 's/^FastQC v//' )
    END_VERSIONS
    """

    stub:
    // Emit an output per input read file so paired- and single-end wiring match.
    """
    for fq in ${reads}; do
        base=\$( basename "\$fq" | sed -E 's/\\.(fastq|fq)(\\.gz)?\$//' )
        touch "\${base}_fastqc.html" "\${base}_fastqc.zip"
    done
    echo '"${task.process}": {fastqc: stub}' > versions.yml
    """
}
