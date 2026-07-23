//
// Validate the samplesheet and turn it into a channel of [ meta, [fastqs] ].
//
// H5: a sample may appear on more than one row (one per sequencing lane). Rows
// are grouped by sample; single-lane samples pass through unchanged, multi-lane
// samples are concatenated into one FASTQ per read end by CAT_FASTQ. The
// single-lane path is byte-for-byte the pre-H5 behaviour, so CI is unaffected.
//

include { SAMPLESHEET_CHECK } from '../../modules/local/samplesheet_check'
include { CAT_FASTQ         } from '../../modules/local/cat_fastq'

workflow INPUT_CHECK {
    take:
    samplesheet // path: input samplesheet CSV

    main:
    ch_versions = Channel.empty()

    SAMPLESHEET_CHECK ( samplesheet )
    ch_versions = ch_versions.mix( SAMPLESHEET_CHECK.out.versions )

    // One entry per samplesheet row: [ meta, [fastqs] ]. Lanes of one sample
    // share an identical meta map, so groupTuple gathers them together.
    ch_rows = SAMPLESHEET_CHECK.out.csv
        .splitCsv ( header: true, sep: ',' )
        .map { row -> create_fastq_channel(row) }

    ch_grouped = ch_rows
        .groupTuple()                         // [ meta, [[l1_r1,l1_r2],[l2_r1,...]] ]
        .branch { meta, reads ->
            single: reads.size() == 1         // one lane -> passthrough
            multi:  true                      // >1 lane  -> merge
        }

    // Single-lane: unwrap the one-element grouping back to [ meta, [fastqs] ].
    ch_single = ch_grouped.single.map { meta, reads -> [ meta, reads.flatten() ] }

    // Multi-lane: flatten all lanes into one list; CAT_FASTQ merges per read end.
    CAT_FASTQ ( ch_grouped.multi.map { meta, reads -> [ meta, reads.flatten() ] } )
    ch_versions = ch_versions.mix( CAT_FASTQ.out.versions )

    reads = ch_single.mix( CAT_FASTQ.out.reads )

    emit:
    reads                        // channel: [ val(meta), [ path(reads) ] ]
    versions = ch_versions       // channel: [ path(versions.yml) ]
}

// Build a meta map + typed FASTQ file list from one normalized samplesheet row.
def create_fastq_channel(LinkedHashMap row) {
    def meta = [:]
    meta.id         = row.sample
    meta.single_end = row.single_end.toBoolean()
    meta.status     = (row.status ?: '0').toInteger()
    meta.patient    = row.patient ?: row.sample     // pairing id for somatic (M7)

    if (meta.single_end) {
        return [ meta, [ file(row.fastq_1, checkIfExists: true) ] ]
    }
    return [ meta, [ file(row.fastq_1, checkIfExists: true),
                     file(row.fastq_2, checkIfExists: true) ] ]
}
