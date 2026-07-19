//
// Read QC: FastQC on the raw reads and fastp for adapter/quality trimming.
// Emits the trimmed reads for downstream alignment (M2) plus the report files
// that the top-level MultiQC aggregates alongside every other stage.
//

include { FASTQC } from '../../modules/local/fastqc'
include { FASTP  } from '../../modules/local/fastp'

workflow FASTQ_QC {
    take:
    reads // channel: [ val(meta), [ path(reads) ] ]

    main:
    ch_versions     = Channel.empty()
    ch_multiqc_files = Channel.empty()

    FASTQC ( reads )
    ch_versions      = ch_versions.mix( FASTQC.out.versions.first() )
    ch_multiqc_files = ch_multiqc_files.mix( FASTQC.out.zip.map { meta, zip -> zip } )

    FASTP ( reads )
    ch_versions      = ch_versions.mix( FASTP.out.versions.first() )
    ch_multiqc_files = ch_multiqc_files.mix( FASTP.out.json.map { meta, json -> json } )

    emit:
    trimmed_reads = FASTP.out.reads    // channel: [ val(meta), [ path(reads) ] ]
    multiqc_files = ch_multiqc_files   // channel: path(report files)
    versions      = ch_versions
}
