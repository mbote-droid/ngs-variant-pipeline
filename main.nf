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
include { VALIDATE_INPUTS } from './modules/local/validate_inputs'
include { FASTQ_QC       } from './subworkflows/local/fastq_qc'
include { PREPARE_GENOME } from './subworkflows/local/prepare_genome'
include { ALIGN          } from './subworkflows/local/align'
include { ALIGN_LONG     } from './subworkflows/local/align_long'
include { CALL_VARIANTS  } from './subworkflows/local/call_variants'
include { CALL_VARIANTS_LONG } from './subworkflows/local/call_variants_long'
include { CALL_VARIANTS_SOMATIC } from './subworkflows/local/call_variants_somatic'
include { JOINT_GENOTYPING } from './subworkflows/local/joint_genotyping'
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

    // ---- H8: input-hardening gate (opt-in) ------------------------------
    // Validate FASTQ integrity + size/decompression-bomb caps BEFORE any heavy
    // tool touches the data. Downstream reads join on the validation report, so
    // alignment only proceeds once a sample passes (a failure aborts the run).
    ch_reads = INPUT_CHECK.out.reads
    if ( params.validate_inputs ) {
        VALIDATE_INPUTS ( ch_reads )
        ch_versions      = ch_versions.mix( VALIDATE_INPUTS.out.versions.first() )
        ch_multiqc_files = ch_multiqc_files.mix( VALIDATE_INPUTS.out.report.map { meta, f -> f } )
        ch_reads = ch_reads
            .join( VALIDATE_INPUTS.out.report )
            .map { meta, reads, report -> [ meta, reads ] }
    }

    // ---- M2/M3: long-read path (opt-in) OR the short-read path ----------
    if ( params.long_read ) {
        // ---- M9: long-read (minimap2 -> Clair3 + Sniffles2) -------------
        // Long reads skip fastp/MarkDuplicates/BQSR (Illumina-specific) and go
        // straight to minimap2. Clair3 calls small variants (into the report
        // path); Sniffles2 calls structural variants (separate SV VCF).
        def lr_preset   = params.long_read_platform == 'pacbio' ? 'map-hifi' : 'map-ont'
        def lr_platform = params.long_read_platform == 'pacbio' ? 'hifi' : 'ont'

        ALIGN_LONG (
            ch_reads,
            PREPARE_GENOME.out.fasta,
            PREPARE_GENOME.out.fai,
            lr_preset
        )
        ch_versions      = ch_versions.mix( ALIGN_LONG.out.versions )
        ch_multiqc_files = ch_multiqc_files
            .mix( ALIGN_LONG.out.flagstat.map { meta, f -> f } )
            .mix( ALIGN_LONG.out.mosdepth_global.map { meta, f -> f } )

        ch_clair3_model = params.clair3_model
            ? Channel.fromPath(params.clair3_model, checkIfExists: true)
            : Channel.value([])

        CALL_VARIANTS_LONG (
            ALIGN_LONG.out.bam,
            PREPARE_GENOME.out.fasta,
            PREPARE_GENOME.out.fai,
            lr_platform,
            ch_clair3_model
        )
        ch_versions      = ch_versions.mix( CALL_VARIANTS_LONG.out.versions )
        ch_multiqc_files = ch_multiqc_files.mix( CALL_VARIANTS_LONG.out.stats.map { meta, f -> f } )
        ch_calls_vcf     = CALL_VARIANTS_LONG.out.vcf
    }
    else {
        // ---- M1: read QC/trim (short-read only) -------------------------
        FASTQ_QC ( ch_reads )
        ch_versions      = ch_versions.mix( FASTQ_QC.out.versions )
        ch_multiqc_files = ch_multiqc_files.mix( FASTQ_QC.out.multiqc_files )

        // ---- M2: alignment + BAM QC -------------------------------------
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

        // ---- M3 / M7 / H5: variant calling (germline / somatic / joint) -
        if ( params.somatic ) {
            // Somatic: pair tumor/normal by patient and run Mutect2 (opt-in).
            ch_pon      = params.pon ? Channel.fromPath(params.pon, checkIfExists: true).first() : Channel.value([])
            ch_pon_tbi  = params.pon ? Channel.fromPath("${params.pon}.tbi", checkIfExists: true).first() : Channel.value([])
            ch_germ     = params.germline_resource ? Channel.fromPath(params.germline_resource, checkIfExists: true).first() : Channel.value([])
            ch_germ_tbi = params.germline_resource ? Channel.fromPath("${params.germline_resource}.tbi", checkIfExists: true).first() : Channel.value([])

            CALL_VARIANTS_SOMATIC (
                ALIGN.out.bam,
                PREPARE_GENOME.out.fasta,
                PREPARE_GENOME.out.fai,
                PREPARE_GENOME.out.dict,
                ch_pon, ch_pon_tbi, ch_germ, ch_germ_tbi
            )
            ch_versions  = ch_versions.mix( CALL_VARIANTS_SOMATIC.out.versions )
            ch_calls_vcf = CALL_VARIANTS_SOMATIC.out.vcf
        }
        else if ( params.joint ) {
            // ---- H5: cohort joint genotyping (opt-in) -------------------
            // Per-sample GVCFs -> CombineGVCFs -> one GenotypeGVCFs over the
            // whole cohort. Emits a single multi-sample VCF; per-sample reports
            // are sliced out downstream by genotype column (see report block).
            JOINT_GENOTYPING (
                ALIGN.out.bam,
                PREPARE_GENOME.out.fasta,
                PREPARE_GENOME.out.fai,
                PREPARE_GENOME.out.dict,
                params.cohort_id
            )
            ch_versions      = ch_versions.mix( JOINT_GENOTYPING.out.versions )
            ch_multiqc_files = ch_multiqc_files.mix( JOINT_GENOTYPING.out.stats.map { meta, f -> f } )
            ch_calls_vcf     = JOINT_GENOTYPING.out.vcf
            // Remember the per-sample identities for per-sample reporting.
            ch_cohort_samples = ALIGN.out.bam.map { meta, bam, bai -> meta }
        }
        else {
            CALL_VARIANTS (
                ALIGN.out.bam,
                PREPARE_GENOME.out.fasta,
                PREPARE_GENOME.out.fai,
                PREPARE_GENOME.out.dict
            )
            ch_versions      = ch_versions.mix( CALL_VARIANTS.out.versions )
            ch_multiqc_files = ch_multiqc_files.mix( CALL_VARIANTS.out.stats.map { meta, f -> f } )
            ch_calls_vcf     = CALL_VARIANTS.out.vcf

            // ---- H4: accuracy benchmarking (opt-in, germline) -----------
            if ( params.benchmark ) {
                if ( !params.truth ) {
                    error "Benchmarking (--benchmark) requires --truth <truth.vcf> " +
                          "(and optionally --truth_bed <regions.bed>)."
                }
                BENCHMARK (
                    ch_calls_vcf,
                    PREPARE_GENOME.out.fasta,
                    PREPARE_GENOME.out.fai
                )
                ch_versions      = ch_versions.mix( BENCHMARK.out.versions )
                ch_multiqc_files = ch_multiqc_files.mix( BENCHMARK.out.tsv.map { meta, f -> f } )
            }
        }
    }

    // ---- M4: annotation -------------------------------------------------
    ch_report_vcf = ch_calls_vcf
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
            ch_calls_vcf,
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
        // Default: one report per callset entry. In joint mode the callset is a
        // single multi-sample VCF, so fan it out into one report per sample
        // (the prioritizer selects each sample's genotype column via --sample)
        // plus one whole-cohort report.
        if ( params.joint ) {
            ch_per_sample_vcf = ch_cohort_samples
                .combine( ch_report_vcf )                       // [ smeta, cmeta, vcf, tbi ]
                .map { smeta, cmeta, vcf, tbi -> [ smeta, vcf, tbi ] }
            ch_report_input = ch_per_sample_vcf.mix( ch_report_vcf )
        }
        else {
            ch_report_input = ch_report_vcf
        }

        REPORT ( ch_report_input, params.report_llm )
        ch_versions = ch_versions.mix( REPORT.out.versions )
    }

    // ---- Provenance: collate tool versions ------------------------------
    ch_versions
        .unique()
        .collectFile( name: 'software_versions.yml', storeDir: "${params.outdir}/pipeline_info" )

    // ---- MultiQC: one report aggregating every stage --------------------
    MULTIQC ( ch_multiqc_files.collect() )
}
