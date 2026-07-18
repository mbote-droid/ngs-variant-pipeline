#!/usr/bin/env nextflow

/*
 * ngs-variant-pipeline
 * ====================
 * Reproducible Nextflow NGS variant-analysis pipeline: raw sequencing reads to
 * an AI-generated, evidence-cited clinical report. Built module by module
 * (see ROADMAP.md). Germline short-read first, then somatic, then long-read.
 *
 * Current entry stage (M1): Input + QC
 *   samplesheet -> validate -> FastQC + fastp -> MultiQC
 */

nextflow.enable.dsl = 2

include { INPUT_CHECK } from './subworkflows/local/input_check'
include { FASTQ_QC    } from './subworkflows/local/fastq_qc'

workflow {
    // Parameter checks
    if (!params.input) {
        error "No input samplesheet provided. Use --input <samplesheet.csv> " +
              "(see assets/samplesheet_test.csv for the expected format)."
    }

    ch_versions = Channel.empty()

    // Validate the samplesheet -> channel of [ meta, [fastqs] ]
    INPUT_CHECK ( file(params.input, checkIfExists: true) )
    ch_versions = ch_versions.mix( INPUT_CHECK.out.versions )

    // Raw-read QC + trimming + aggregated report
    FASTQ_QC ( INPUT_CHECK.out.reads )
    ch_versions = ch_versions.mix( FASTQ_QC.out.versions )

    // Collate tool versions for provenance
    ch_versions
        .unique()
        .collectFile( name: 'software_versions.yml', storeDir: "${params.outdir}/pipeline_info" )
}
