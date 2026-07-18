process SAMPLESHEET_CHECK {
    tag "$samplesheet"
    label 'process_single'

    conda 'conda-forge::python=3.11'
    container 'python:3.11-slim'

    input:
    path samplesheet

    output:
    path '*.valid.csv',  emit: csv
    path 'versions.yml', emit: versions

    script:  // check_samplesheet.py lives in bin/, which Nextflow puts on PATH
    """
    check_samplesheet.py ${samplesheet} samplesheet.valid.csv

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        python: \$( python --version 2>&1 | sed 's/Python //g' )
    END_VERSIONS
    """

    stub:  // still runs the real (stdlib-only) validator so downstream channels are well-formed
    """
    check_samplesheet.py ${samplesheet} samplesheet.valid.csv
    echo '"${task.process}": {python: stub}' > versions.yml
    """
}
