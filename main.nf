#!/usr/bin/env nextflow

/*
 * ngs-variant-pipeline
 * ====================
 * Reproducible Nextflow NGS variant-analysis pipeline: raw sequencing reads to
 * an AI-generated, evidence-cited clinical report. Built module by module
 * (see ROADMAP.md). Germline short-read first, then somatic, then long-read.
 *
 * Cascade: samplesheet -> QC/trim -> align -> variant call -> annotate ->
 *          prioritize -> report, with a single MultiQC aggregating every stage.
 */

nextflow.enable.dsl = 2

include { INPUT_CHECK    } from './subworkflows/local/input_check'
include { FASTQ_QC       } from './subworkflows/local/fastq_qc'
include { PREPARE_GENOME } from './subworkflows/local/prepare_genome'
include { ALIGN          } from './subworkflows/local/align'
include { CALL_VARIANTS  } from './subworkflows/local/call_variants'
include { ANNOTATE       } from './subworkflows/local/annotate'
include { BENCHMARK      } from './subworkflows/local/benchmark'
include { REPORT         } from './subworkflows/local/report'
include { MULTIQC        } from './modules/local/multiqc'

workflow {
    // ---- H2: resolve --genome into reference params (explicit params win) -
    // A known-genome key (conf/genomes.config) fills reference assets so a real
    // run needs only `--genome GRCh38`. Anything passed explicitly overrides the
    // map, so the synthetic `test` profile (which sets --fasta) is unaffected.
    def genome_attrs = ( params.genome && params.genomes instanceof Map
                         && params.genomes.containsKey(params.genome) )
        ? params.genomes[params.genome] : [:]
    def ref_fasta       = params.fasta       ?: genome_attrs.fasta
    def ref_known_sites = params.known_sites ?: genome_attrs.known_sites
    def ref_snpeff_db   = params.snpeff_db   ?: genome_attrs.snpeff_db

    // ---- Parameter checks ------------------------------------------------
    if (!params.input) {
        error "No input samplesheet provided. Use --input <samplesheet.csv> " +
              "(see assets/samplesheet_test.csv for the expected format)."
    }
    if (!ref_fasta) {
        error "No reference provided. Use --fasta <reference.fa> or " +
              "--genome <key> (see conf/genomes.config)."
    }

    ch_versions      = Channel.empty()
    ch_multiqc_files = Channel.empty()

    // ---- Reference indices (once) ---------------------------------------
    ch_fasta       = Channel.fromPath(ref_fasta, checkIfExists: true)
    ch_known_sites = ref_known_sites
        ? Channel.fromPath(ref_known_sites, checkIfExists: true)
        : Channel.empty()

    PREPARE_GENOME ( ch_fasta, ch_known_sites )
    ch_versions = ch_versions.mix( PREPARE_GENOME.out.versions )

    // ---- M1: input + QC --------------------------------------------------
    INPUT_CHECK ( file(params.input, checkIfExists: true) )
    ch_versions = ch_versions.mix( INPUT_CHECK.out.versions )

    FASTQ_QC ( INPUT_CHECK.out.reads )
    ch_versions      = ch_versions.mix( FASTQ_QC.out.versions )
    ch_multiqc_files = ch_multiqc_files.mix( FASTQ_QC.out.multiqc_files )

    // ---- M2: alignment + BAM QC -----------------------------------------
    run_bqsr = !params.skip_bqsr && (ref_known_sites as boolean)
    ALIGN (
        FASTQ_QC.out.trimmed_reads,
        PREPARE_GENOME.out.fasta,
        PREPARE_GENOME.out.fai,
        PREPARE_GENOME.out.dict,
        PREPARE_GENOME.out.bwa_index,
        run_bqsr ? PREPARE_GENOME.out.known_sites : Channel.value([ [], [] ]),
        run_bqsr
    )
    ch_versions      = ch_versions.mix( ALIGN.out.versions )
    ch_multiqc_files = ch_multiqc_files
        .mix( ALIGN.out.flagstat.map { meta, f -> f } )
        .mix( ALIGN.out.markdup_metrics.map { meta, f -> f } )
        .mix( ALIGN.out.mosdepth_global.map { meta, f -> f } )

    // ---- M3: germline variant calling -----------------------------------
    CALL_VARIANTS (
        ALIGN.out.bam,
        PREPARE_GENOME.out.fasta,
        PREPARE_GENOME.out.fai,
        PREPARE_GENOME.out.dict
    )
    ch_versions      = ch_versions.mix( CALL_VARIANTS.out.versions )
    ch_multiqc_files = ch_multiqc_files.mix( CALL_VARIANTS.out.stats.map { meta, f -> f } )

    // ---- H4: accuracy benchmarking (opt-in) -----------------------------
    if ( params.benchmark ) {
        if ( !params.truth ) {
            error "Benchmarking (--benchmark) requires --truth <truth.vcf> " +
                  "(and optionally --truth_bed <regions.bed>)."
        }
        BENCHMARK (
            CALL_VARIANTS.out.vcf,
            PREPARE_GENOME.out.fasta,
            PREPARE_GENOME.out.fai
        )
        ch_versions      = ch_versions.mix( BENCHMARK.out.versions )
        ch_multiqc_files = ch_multiqc_files.mix( BENCHMARK.out.tsv.map { meta, f -> f } )
    }

    // ---- M4: annotation -------------------------------------------------
    ch_report_vcf = CALL_VARIANTS.out.vcf
    if ( !params.skip_annotation ) {
        // The offline SnpEff DB build needs a GFF3; a downloaded/prebuilt cache
        // or the VEP path does not.
        boolean snpeff_build = params.annotator == 'snpeff' &&
            !params.download_snpeff_cache
        if ( snpeff_build && !params.gff ) {
            error "Offline SnpEff DB build requires --gff <genes.gff3>. Provide " +
                  "--gff, or use --download_snpeff_cache / --annotator vep, or " +
                  "run with --skip_annotation."
        }
        ANNOTATE (
            CALL_VARIANTS.out.vcf,
            PREPARE_GENOME.out.fasta,
            params.gff ? Channel.fromPath(params.gff, checkIfExists: true)
                       : Channel.value([]),
            ref_snpeff_db
        )
        ch_versions      = ch_versions.mix( ANNOTATE.out.versions )
        ch_multiqc_files = ch_multiqc_files.mix( ANNOTATE.out.report.map { meta, f -> f } )
        ch_report_vcf    = ANNOTATE.out.vcf
    }

    // ---- M5 + M6: prioritization + report -------------------------------
    if ( !params.skip_report ) {
        REPORT ( ch_report_vcf, params.report_llm )
        ch_versions = ch_versions.mix( REPORT.out.versions )
    }

    // ---- Provenance: collate tool versions ------------------------------
    ch_versions
        .unique()
        .collectFile( name: 'software_versions.yml', storeDir: "${params.outdir}/pipeline_info" )

    // ---- MultiQC: one report aggregating every stage --------------------
    MULTIQC ( ch_multiqc_files.collect() )
}
