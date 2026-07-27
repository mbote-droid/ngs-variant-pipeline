process VALIDATE_INPUTS {
    tag "$meta.id"
    label 'process_single'

    conda 'conda-forge::python=3.11'
    container 'python:3.11-slim'

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path('*.validation.txt'), emit: report
    path 'versions.yml',                       emit: versions

    // H8: pre-flight input gate. validate_inputs.py rejects truncated/malformed
    // FASTQ and decompression bombs; a non-zero exit fails the task, and because
    // downstream stages join on this report, alignment never starts on bad input.
    script:  // validate_inputs.py is on PATH via bin/
    def prefix   = task.ext.prefix ?: "${meta.id}"
    def args     = task.ext.args ?: ''      // --max-gb / --max-ratio from params
    def readList = (reads instanceof List ? reads : [reads]).join(' ')
    """
    validate_inputs.py ${readList} ${args} --report ${prefix}.validation.txt

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$( python --version 2>&1 | sed 's/Python //g' )
    END_VERSIONS
    """

    stub:  // runs the real (stdlib-only) validator on the staged reads
    def prefix   = task.ext.prefix ?: "${meta.id}"
    def readList = (reads instanceof List ? reads : [reads]).join(' ')
    """
    validate_inputs.py ${readList} --report ${prefix}.validation.txt
    echo '"${task.process}": {python: stub}' > versions.yml
    """
}
