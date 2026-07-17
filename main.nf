#!/usr/bin/env nextflow

/*
 * Genome-to-Report Pipeline
 * =========================
 * Module 0 scaffold. This is a minimal, end-to-end smoke test that proves the
 * Nextflow + Docker toolchain works before any real genomics modules are added.
 * Real stages (QC -> alignment -> variant calling -> annotation -> report) are
 * added module by module per ROADMAP.md.
 */

nextflow.enable.dsl = 2

process SMOKE_TEST {
    tag 'smoke'
    container 'ubuntu:22.04'
    publishDir "${params.outdir}", mode: 'copy'

    input:
    val greeting

    output:
    path 'smoke_test.txt'

    script:
    """
    {
      echo "${greeting}"
      echo "utc_time : \$(date -u)"
      echo "host     : \$(uname -srm)"
      echo "container: \$(grep PRETTY_NAME /etc/os-release | cut -d= -f2 | tr -d '\\"')"
    } > smoke_test.txt
    cat smoke_test.txt
    """
}

workflow {
    SMOKE_TEST( Channel.value(params.greeting) )
}
