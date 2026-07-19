process BWAMEM2_INDEX {
    tag "$fasta"
    label 'process_high'

    conda 'bioconda::bwa-mem2=2.2.1'
    container 'biocontainers/bwa-mem2:2.2.1--he513fc3_0'

    input:
    path fasta

    output:
    path 'bwamem2',      emit: index
    path 'versions.yml', emit: versions

    script:
    """
    mkdir bwamem2
    bwa-mem2 index -p bwamem2/${fasta} ${fasta}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bwa-mem2: \$( bwa-mem2 version 2>&1 | head -1 )
    END_VERSIONS
    """

    stub:
    """
    mkdir bwamem2
    touch bwamem2/${fasta}.0123 bwamem2/${fasta}.amb bwamem2/${fasta}.ann
    touch bwamem2/${fasta}.bwt.2bit.64 bwamem2/${fasta}.pac
    echo '"${task.process}": {bwa-mem2: stub}' > versions.yml
    """
}
