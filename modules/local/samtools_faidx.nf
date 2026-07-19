process SAMTOOLS_FAIDX {
    tag "$fasta"
    label 'process_single'

    conda 'bioconda::samtools=1.19.2'
    container 'biocontainers/samtools:1.19.2--h50ea8bc_0'

    input:
    path fasta

    output:
    path '*.fai',        emit: fai
    path 'versions.yml', emit: versions

    script:
    """
    samtools faidx ${fasta}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        samtools: \$( samtools --version | head -1 | sed 's/samtools //' )
    END_VERSIONS
    """

    stub:
    """
    touch ${fasta}.fai
    echo '"${task.process}": {samtools: stub}' > versions.yml
    """
}
