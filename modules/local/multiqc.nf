process MULTIQC {
    label 'process_single'

    conda 'bioconda::multiqc=1.21'
    container 'biocontainers/multiqc:1.21--pyhdfd78af_0'

    input:
    path multiqc_files, stageAs: '?/*'

    output:
    path '*multiqc_report.html', emit: report
    path 'multiqc_data',         emit: data
    path 'versions.yml',         emit: versions

    script:
    def args = task.ext.args ?: ''
    """
    multiqc --force ${args} .

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        multiqc: \$( multiqc --version | sed -e 's/multiqc, version //g' )
    END_VERSIONS
    """

    stub:
    """
    mkdir multiqc_data
    touch multiqc_report.html
    echo '"${task.process}": {multiqc: stub}' > versions.yml
    """
}
