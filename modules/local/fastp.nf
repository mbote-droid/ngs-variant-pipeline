process FASTP {
    tag "$meta.id"
    label 'process_medium'

    conda 'bioconda::fastp=0.23.4'
    container 'biocontainers/fastp:0.23.4--h5f740d0_0'

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path('*.fastp.fastq.gz'), emit: reads
    tuple val(meta), path('*.fastp.json'),     emit: json
    tuple val(meta), path('*.fastp.html'),     emit: html
    tuple val(meta), path('*.fastp.log'),      emit: log
    path 'versions.yml',                       emit: versions

    script:
    def prefix = task.ext.prefix ?: "${meta.id}"
    def args   = task.ext.args ?: ''
    if (meta.single_end) {
        """
        fastp \\
            --in1 ${reads} \\
            --out1 ${prefix}.fastp.fastq.gz \\
            --json ${prefix}.fastp.json \\
            --html ${prefix}.fastp.html \\
            --thread ${task.cpus} \\
            ${args} \\
            2> ${prefix}.fastp.log

        cat <<-END_VERSIONS > versions.yml
        "${task.process}":
            fastp: \$( fastp --version 2>&1 | sed -e 's/fastp //g' )
        END_VERSIONS
        """
    } else {
        """
        fastp \\
            --in1 ${reads[0]} \\
            --in2 ${reads[1]} \\
            --out1 ${prefix}_1.fastp.fastq.gz \\
            --out2 ${prefix}_2.fastp.fastq.gz \\
            --json ${prefix}.fastp.json \\
            --html ${prefix}.fastp.html \\
            --thread ${task.cpus} \\
            ${args} \\
            2> ${prefix}.fastp.log

        cat <<-END_VERSIONS > versions.yml
        "${task.process}":
            fastp: \$( fastp --version 2>&1 | sed -e 's/fastp //g' )
        END_VERSIONS
        """
    }

    stub:
    def prefix = task.ext.prefix ?: "${meta.id}"
    if (meta.single_end) {
        """
        echo | gzip > ${prefix}.fastp.fastq.gz
        touch ${prefix}.fastp.json ${prefix}.fastp.html ${prefix}.fastp.log
        echo '"${task.process}": {fastp: stub}' > versions.yml
        """
    } else {
        """
        echo | gzip > ${prefix}_1.fastp.fastq.gz
        echo | gzip > ${prefix}_2.fastp.fastq.gz
        touch ${prefix}.fastp.json ${prefix}.fastp.html ${prefix}.fastp.log
        echo '"${task.process}": {fastp: stub}' > versions.yml
        """
    }
}
