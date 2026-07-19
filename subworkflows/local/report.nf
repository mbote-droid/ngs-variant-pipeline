//
// Prioritize annotated variants (M5) and generate the clinical report (M6):
// HTML + JSON + minimal FHIR. Runs fully offline; the LLM narrative is optional.
//

include { PRIORITIZE_VARIANTS } from '../../modules/local/prioritize_variants'
include { GENERATE_REPORT     } from '../../modules/local/generate_report'

workflow REPORT {
    take:
    vcf         // channel: [ meta, annotated_vcf, tbi ]
    enable_llm  // boolean

    main:
    ch_versions = Channel.empty()

    PRIORITIZE_VARIANTS ( vcf )
    ch_versions = ch_versions.mix( PRIORITIZE_VARIANTS.out.versions.first() )

    GENERATE_REPORT ( PRIORITIZE_VARIANTS.out.json, enable_llm )
    ch_versions = ch_versions.mix( GENERATE_REPORT.out.versions.first() )

    emit:
    html            = GENERATE_REPORT.out.html
    report_json     = GENERATE_REPORT.out.report_json
    fhir            = GENERATE_REPORT.out.fhir
    prioritized_tsv = PRIORITIZE_VARIANTS.out.tsv
    versions        = ch_versions
}
