//
// Alignment + BAM post-processing: BWA-MEM2 -> sort -> MarkDuplicates ->
// (optional) BQSR, then alignment QC (samtools flagstat, mosdepth).
// Emits an analysis-ready BAM for variant calling (M3).
//

include { BWAMEM2_MEM            } from '../../modules/local/bwamem2_mem'
include { GATK4_MARKDUPLICATES   } from '../../modules/local/gatk4_markduplicates'
include { GATK4_BASERECALIBRATOR } from '../../modules/local/gatk4_baserecalibrator'
include { GATK4_APPLYBQSR        } from '../../modules/local/gatk4_applybqsr'
include { SAMTOOLS_FLAGSTAT      } from '../../modules/local/samtools_flagstat'
include { MOSDEPTH               } from '../../modules/local/mosdepth'

workflow ALIGN {
    take:
    reads         // channel: [ meta, [reads] ]
    fasta         // value:   path(fasta)
    fai           // value:   path(fai)
    dict          // value:   path(dict)
    bwa_index     // value:   path(index dir)
    known_sites   // value:   [ gz, tbi ] (may be empty)
    run_bqsr      // boolean

    main:
    ch_versions = Channel.empty()

    BWAMEM2_MEM ( reads, bwa_index, fasta )
    ch_versions = ch_versions.mix( BWAMEM2_MEM.out.versions.first() )

    GATK4_MARKDUPLICATES ( BWAMEM2_MEM.out.bam )
    ch_versions = ch_versions.mix( GATK4_MARKDUPLICATES.out.versions.first() )

    if ( run_bqsr ) {
        GATK4_BASERECALIBRATOR ( GATK4_MARKDUPLICATES.out.bam, fasta, fai, dict,
                                 known_sites )
        ch_versions = ch_versions.mix( GATK4_BASERECALIBRATOR.out.versions.first() )

        // join the md BAM with its recal table on meta, then apply BQSR
        ch_applybqsr_in = GATK4_MARKDUPLICATES.out.bam
            .join( GATK4_BASERECALIBRATOR.out.table, by: 0 )
            .map { meta, bam, bai, table -> [ meta, bam, bai, table ] }

        GATK4_APPLYBQSR ( ch_applybqsr_in, fasta, fai, dict )
        ch_versions = ch_versions.mix( GATK4_APPLYBQSR.out.versions.first() )
        ch_bam = GATK4_APPLYBQSR.out.bam
    } else {
        ch_bam = GATK4_MARKDUPLICATES.out.bam
    }

    SAMTOOLS_FLAGSTAT ( ch_bam )
    MOSDEPTH ( ch_bam )
    ch_versions = ch_versions
        .mix( SAMTOOLS_FLAGSTAT.out.versions.first() )
        .mix( MOSDEPTH.out.versions.first() )

    emit:
    bam            = ch_bam                                   // [ meta, bam, bai ]
    flagstat       = SAMTOOLS_FLAGSTAT.out.flagstat
    markdup_metrics = GATK4_MARKDUPLICATES.out.metrics
    mosdepth_summary = MOSDEPTH.out.summary
    mosdepth_global  = MOSDEPTH.out.global_dist
    versions       = ch_versions
}
