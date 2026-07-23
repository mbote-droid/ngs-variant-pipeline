//
// M9: long-read alignment. minimap2 (map-ont / map-hifi) -> sorted, indexed BAM,
// then the same alignment QC (samtools flagstat, mosdepth) as the short-read
// path. No MarkDuplicates/BQSR: PCR-free long-read data is not deduplicated and
// BQSR models are Illumina-specific. Emits an analysis-ready BAM.
//

include { MINIMAP2_ALIGN    } from '../../modules/local/minimap2_align'
include { SAMTOOLS_FLAGSTAT } from '../../modules/local/samtools_flagstat'
include { MOSDEPTH          } from '../../modules/local/mosdepth'

workflow ALIGN_LONG {
    take:
    reads   // channel: [ meta, [reads] ]
    fasta   // value:   path(fasta)
    fai     // value:   path(fai)
    preset  // val:     'map-ont' or 'map-hifi'

    main:
    ch_versions = Channel.empty()

    MINIMAP2_ALIGN ( reads, fasta, preset )
    ch_versions = ch_versions.mix( MINIMAP2_ALIGN.out.versions.first() )

    SAMTOOLS_FLAGSTAT ( MINIMAP2_ALIGN.out.bam )
    MOSDEPTH ( MINIMAP2_ALIGN.out.bam )
    ch_versions = ch_versions
        .mix( SAMTOOLS_FLAGSTAT.out.versions.first() )
        .mix( MOSDEPTH.out.versions.first() )

    emit:
    bam             = MINIMAP2_ALIGN.out.bam          // [ meta, bam, bai ]
    flagstat        = SAMTOOLS_FLAGSTAT.out.flagstat
    mosdepth_global = MOSDEPTH.out.global_dist
    versions        = ch_versions
}
