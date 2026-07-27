//
// H4: accuracy benchmarking. Compare called variants to a truth/gold-standard
// set and report precision / recall / F1 (overall + SNP/INDEL). Two backends:
//   'builtin' - stdlib exact-match concordance (offline, always available)
//   'happy'   - GA4GH hap.py against a real gold standard (e.g. GIAB)
// Opt-in via --benchmark; the default DAG never enters this subworkflow.
//

include { BENCHMARK_VCF } from '../../modules/local/benchmark_vcf'
include { HAPPY         } from '../../modules/local/happy'
include { HAPPY_PARSE   } from '../../modules/local/happy_parse'
include { PLOT_ACCURACY } from '../../modules/local/plot_accuracy'

workflow BENCHMARK {
    take:
    vcf    // channel: [ meta, vcf, tbi ]
    fasta  // value:   path(fasta)
    fai    // value:   path(fai)

    main:
    ch_versions = Channel.empty()

    ch_truth = Channel.fromPath(params.truth, checkIfExists: true).first()
    ch_bed   = params.truth_bed
        ? Channel.fromPath(params.truth_bed, checkIfExists: true).first()
        : Channel.value([])

    if ( params.benchmark_tool == 'happy' ) {
        HAPPY ( vcf, ch_truth, ch_bed, fasta, fai )
        HAPPY_PARSE ( HAPPY.out.summary )
        ch_json     = HAPPY_PARSE.out.json
        ch_tsv      = HAPPY_PARSE.out.tsv
        ch_versions = ch_versions
            .mix( HAPPY.out.versions.first() )
            .mix( HAPPY_PARSE.out.versions.first() )
    }
    else {
        BENCHMARK_VCF ( vcf, ch_truth, ch_bed )
        ch_json     = BENCHMARK_VCF.out.json
        ch_tsv      = BENCHMARK_VCF.out.tsv
        ch_versions = ch_versions.mix( BENCHMARK_VCF.out.versions.first() )
    }

    // Showcase SVGs (PR curve, F1-by-type, genotype confusion) from the metrics.
    PLOT_ACCURACY ( ch_json )
    ch_versions = ch_versions.mix( PLOT_ACCURACY.out.versions.first() )

    emit:
    metrics  = ch_json                // [ meta, benchmark.json ]
    tsv      = ch_tsv                  // [ meta, benchmark.tsv ]
    plots    = PLOT_ACCURACY.out.plots // [ meta, [ *.svg ] ]
    versions = ch_versions
}
