//
// M9: long-read variant calling. Two callers run on the same BAM:
//   * Clair3   -> small variants (SNV/indel); flows into annotation + report.
//   * Sniffles2 -> structural variants; emitted as a separate SV VCF.
// bcftools stats on the Clair3 VCF feeds MultiQC. Opt-in via --long_read; the
// short-read germline/somatic/joint paths are unchanged.
//

include { CLAIR3         } from '../../modules/local/clair3'
include { SNIFFLES2      } from '../../modules/local/sniffles2'
include { BCFTOOLS_STATS } from '../../modules/local/bcftools_stats'

workflow CALL_VARIANTS_LONG {
    take:
    bam       // channel: [ meta, bam, bai ]
    fasta     // value:   path(fasta)
    fai       // value:   path(fai)
    platform  // val:     'ont' or 'hifi'  (Clair3 --platform)
    model     // value:   path(clair3 model dir) or []

    main:
    ch_versions = Channel.empty()

    CLAIR3 ( bam, fasta, fai, platform, model )
    ch_versions = ch_versions.mix( CLAIR3.out.versions.first() )

    BCFTOOLS_STATS ( CLAIR3.out.vcf )
    ch_versions = ch_versions.mix( BCFTOOLS_STATS.out.versions.first() )

    SNIFFLES2 ( bam, fasta )
    ch_versions = ch_versions.mix( SNIFFLES2.out.versions.first() )

    emit:
    vcf      = CLAIR3.out.vcf          // [ meta, vcf, tbi ] small variants
    sv_vcf   = SNIFFLES2.out.sv_vcf    // [ meta, vcf ]     structural variants
    stats    = BCFTOOLS_STATS.out.stats
    versions = ch_versions
}
