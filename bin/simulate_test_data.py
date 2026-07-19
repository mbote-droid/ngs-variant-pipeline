#!/usr/bin/env python3
"""
Generate a tiny, fully synthetic, deterministic test dataset for the pipeline.

Everything here is invented - it is NOT derived from any real genome or person.
Its only purpose is to exercise the pipeline end to end (align -> call -> annotate
-> prioritize -> report) offline, on a low-RAM host, in seconds.

It writes, under an output directory:
  reference/test_ref.fa       one ~12 kb contig ("testchr") with a small gene model
  reference/test_ref.gff3     a gene/transcript/CDS model for SnpEff annotation
  reads/sample1_R1.fastq      paired-end reads simulated FROM the reference ...
  reads/sample1_R2.fastq      ... at ~35x, with known variants spiked in
  known_sites.vcf             a dbSNP-like "known sites" VCF for GATK BQSR
  truth.vcf                   the variants actually introduced (for validation)

Design choices that make the downstream stages meaningful:
  * Reads are simulated from the reference, so BWA-MEM2 can align them and
    HaplotypeCaller can recover the spiked variants.
  * A fraction of fragments are shorter than the read length, so the reads read
    through into the adapter and fastp has real adapter to trim.
  * Insert sizes give R1/R2 genuine overlap, which is how paired-end adapter
    detection works.
  * Variants sit inside the CDS so SnpEff reports coding consequences.

Deterministic: a fixed seed means the committed data can be regenerated exactly.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

CONTIG = "testchr"
COMPLEMENT = str.maketrans("ACGTN", "TGCAN")

# Illumina TruSeq adapters (public, standard sequences) for read-through trimming.
ADAPTER_R1 = "AGATCGGAAGAGCACACGTCTGAACTCCAGTCA"
ADAPTER_R2 = "AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT"

# Gene model (1-based, inclusive) placed on the reference.
GENE_START, GENE_END = 4000, 4600
CDS_START, CDS_END = 4030, 4570  # CDS phase 0 begins at CDS_START (+ strand)

# Variants are specified by the coding consequence we WANT SnpEff to report, so
# the demo report exercises every prioritization tier. The concrete REF/ALT are
# solved from the generated reference (see resolve_variants).
#   (approx 1-based pos, allele_fraction, zygosity, desired_effect)
VARIANT_SPECS = [
    (4050, 0.5, "het", "stop_gained"),        # -> HIGH impact  (tier 1)
    (4110, 1.0, "hom", "missense_variant"),   # -> MODERATE     (tier 2)
    (4230, 0.5, "het", "synonymous_variant"), # -> LOW          (tier 3)
]

# Standard genetic code (DNA codons).
CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L", "CTT": "L", "CTC": "L",
    "CTA": "L", "CTG": "L", "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V", "TCT": "S", "TCC": "S",
    "TCA": "S", "TCG": "S", "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T", "GCT": "A", "GCC": "A",
    "GCA": "A", "GCG": "A", "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q", "AAT": "N", "AAC": "N",
    "AAA": "K", "AAG": "K", "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W", "CGT": "R", "CGC": "R",
    "CGA": "R", "CGG": "R", "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

# Resolved variants (pos, ref, alt, af, zyg, effect); filled in by main().
RESOLVED: list[tuple] = []


def revcomp(seq: str) -> str:
    return seq.translate(COMPLEMENT)[::-1]


def gen_reference(length: int, rng: random.Random) -> str:
    # ~45% GC, no long homopolymers that would upset aligners.
    bases = "ACGT"
    seq = []
    for _ in range(length):
        seq.append(rng.choices(bases, weights=[28, 22, 22, 28])[0])
    return "".join(seq)


def _classify(ref_codon: str, alt_codon: str) -> str:
    ra, aa = CODON_TABLE.get(ref_codon), CODON_TABLE.get(alt_codon)
    if ra is None or aa is None:
        return "unknown"
    if ra != "*" and aa == "*":
        return "stop_gained"
    if ra == aa:
        return "synonymous_variant"
    if aa != "*":
        return "missense_variant"
    return "other"


def resolve_variants(ref: str) -> list[tuple]:
    """Solve concrete (pos, ref, alt, af, zyg, effect) for each spec.

    Scans forward from the target position within the CDS for the first
    (position, alt base) that yields the desired coding consequence in frame,
    so the outcome is deterministic and matches what SnpEff will report.
    """
    resolved = []
    for target, af, zyg, want in VARIANT_SPECS:
        found = None
        for pos in range(target, CDS_END - 2):
            codon_idx = (pos - CDS_START) // 3
            codon_start = CDS_START + codon_idx * 3          # 1-based
            codon = ref[codon_start - 1:codon_start + 2]
            if len(codon) < 3:
                continue
            within = pos - codon_start                        # 0..2
            ref_base = ref[pos - 1]
            for alt in "ACGT":
                if alt == ref_base:
                    continue
                mutated = list(codon)
                mutated[within] = alt
                if _classify(codon, "".join(mutated)) == want:
                    found = (pos, ref_base, alt, af, zyg, want)
                    break
            if found:
                break
        if not found:
            raise RuntimeError(f"could not place a {want} near {target}")
        resolved.append(found)
    return resolved


def wrap(seq: str, width: int = 60) -> str:
    return "\n".join(seq[i:i + width] for i in range(0, len(seq), width))


def write_reference(out: Path, ref: str) -> None:
    (out / "reference").mkdir(parents=True, exist_ok=True)
    fa = out / "reference" / "test_ref.fa"
    fa.write_text(f">{CONTIG} synthetic test contig\n{wrap(ref)}\n", encoding="utf-8")


def write_gff3(out: Path) -> None:
    gff = out / "reference" / "test_ref.gff3"
    lines = [
        "##gff-version 3",
        f"##sequence-region {CONTIG} 1 {len(_REF_CACHE[0])}",
        f"{CONTIG}\tsim\tgene\t{GENE_START}\t{GENE_END}\t.\t+\t.\tID=gene_TESTG;Name=TESTG",
        f"{CONTIG}\tsim\tmRNA\t{GENE_START}\t{GENE_END}\t.\t+\t.\tID=tx_TESTG;Parent=gene_TESTG;Name=TESTG-201",
        f"{CONTIG}\tsim\tCDS\t{CDS_START}\t{CDS_END}\t.\t+\t0\tID=cds_TESTG;Parent=tx_TESTG",
    ]
    gff.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _vcf_header() -> str:
    return (
        "##fileformat=VCFv4.2\n"
        f"##contig=<ID={CONTIG},length={len(_REF_CACHE[0])}>\n"
        '##INFO=<ID=AF,Number=A,Type=Float,Description="Allele frequency">\n'
        '##FILTER=<ID=PASS,Description="All filters passed">\n'
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n'
    )


def write_known_and_truth(out: Path, ref: str) -> None:
    truth_rows, known_rows = [], []
    for i, (pos, ref_base, alt, af, zyg, _effect) in enumerate(RESOLVED, start=1):
        gt = "1/1" if zyg == "hom" else "0/1"
        truth_rows.append(
            f"{CONTIG}\t{pos}\t.\t{ref_base}\t{alt}\t.\tPASS\tAF={af}\tGT\t{gt}"
        )
        known_rows.append(
            f"{CONTIG}\t{pos}\trs{9000+i}\t{ref_base}\t{alt}\t.\t.\tAF={af}"
        )
    # Extra "known" sites (no reads carry them) so BQSR has context. REF/ALT are
    # derived from the actual reference base so the VCF is internally consistent.
    for j, pos in enumerate((2500, 8000), start=1):
        rb = ref[pos - 1]
        ab = next(b for b in "ACGT" if b != rb)
        known_rows.append(f"{CONTIG}\t{pos}\trs{9100+j}\t{rb}\t{ab}\t.\t.\tAF=0.1")

    header = _vcf_header()
    cols = "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO"
    (out / "truth.vcf").write_text(
        header + cols + "\tFORMAT\tsample1\n" + "\n".join(truth_rows) + "\n",
        encoding="utf-8",
    )
    (out / "known_sites.vcf").write_text(
        header + cols + "\n" + "\n".join(sorted(known_rows, key=lambda r: int(r.split("\t")[1]))) + "\n",
        encoding="utf-8",
    )


def _qual_string(n: int, rng: random.Random) -> str:
    # High quality (~Q37) tapering toward the 3' end, with slight jitter.
    out = []
    for i in range(n):
        base = 37 - int(12 * (i / n) ** 2)  # gentle 3' drop
        q = max(2, min(40, base + rng.randint(-2, 2)))
        out.append(chr(33 + q))
    return "".join(out)


def _mutate_fragment(frag: str, frag_start: int, rng: random.Random) -> str:
    """Apply spiked variants (by allele fraction) to a fragment covering them."""
    chars = list(frag)
    for pos, ref_base, alt, af, _z, _effect in RESOLVED:
        idx = (pos - 1) - frag_start  # 0-based within fragment
        if 0 <= idx < len(chars) and rng.random() < af:
            chars[idx] = alt
    return "".join(chars)


def _seq_errors(read: str, rng: random.Random, rate: float = 0.001) -> str:
    if rate <= 0:
        return read
    chars = list(read)
    for i, b in enumerate(chars):
        if b != "N" and rng.random() < rate:
            chars[i] = rng.choice([x for x in "ACGT" if x != b])
    return "".join(chars)


def simulate_reads(
    out: Path, ref: str, coverage: int, read_len: int, rng: random.Random
) -> int:
    (out / "reads").mkdir(parents=True, exist_ok=True)
    genome_len = len(ref)
    n_pairs = max(1, (genome_len * coverage) // (2 * read_len))

    r1_lines, r2_lines = [], []
    for i in range(n_pairs):
        # ~15% short fragments (< read_len) to trigger adapter read-through.
        if rng.random() < 0.15:
            frag_len = rng.randint(60, read_len - 5)
        else:
            frag_len = rng.randint(read_len + 40, 350)
        frag_len = min(frag_len, genome_len)
        start = rng.randint(0, genome_len - frag_len)
        frag = ref[start:start + frag_len]
        frag = _mutate_fragment(frag, start, rng)

        # R1 from the 5' end (forward), R2 from the 3' end (reverse complement).
        if frag_len >= read_len:
            s1 = frag[:read_len]
            s2 = revcomp(frag[-read_len:])
        else:  # read-through: pad past the insert with adapter
            s1 = frag + ADAPTER_R1[: read_len - frag_len]
            s2 = revcomp(frag) + ADAPTER_R2[: read_len - frag_len]

        s1 = _seq_errors(s1, rng)
        s2 = _seq_errors(s2, rng)
        rid = f"{CONTIG}_{start + 1}_{start + frag_len}_{i}"
        r1_lines.append(f"@{rid}/1\n{s1}\n+\n{_qual_string(len(s1), rng)}\n")
        r2_lines.append(f"@{rid}/2\n{s2}\n+\n{_qual_string(len(s2), rng)}\n")

    (out / "reads" / "sample1_R1.fastq").write_text("".join(r1_lines), encoding="utf-8")
    (out / "reads" / "sample1_R2.fastq").write_text("".join(r2_lines), encoding="utf-8")
    return n_pairs


# gen_reference result is needed by several writers; stash it once generated.
_REF_CACHE: list[str] = [""]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulate a tiny test dataset.")
    parser.add_argument("--outdir", type=Path, default=Path("assets/test_data"))
    parser.add_argument("--length", type=int, default=12000, help="reference length (bp)")
    parser.add_argument("--coverage", type=int, default=35)
    parser.add_argument("--read-len", type=int, default=100)
    parser.add_argument("--seed", type=int, default=53)
    args = parser.parse_args(argv)

    rng = random.Random(args.seed)
    ref = gen_reference(args.length, rng)
    _REF_CACHE[0] = ref
    RESOLVED[:] = resolve_variants(ref)

    write_reference(args.outdir, ref)
    write_gff3(args.outdir)
    write_known_and_truth(args.outdir, ref)
    n_pairs = simulate_reads(args.outdir, ref, args.coverage, args.read_len, rng)

    spiked = ", ".join(f"{p}{r}>{a}({e})" for p, r, a, _af, _z, e in RESOLVED)
    print(  # noqa: T201  (dev-only data generator, not pipeline runtime)
        f"reference: {args.length} bp ({CONTIG}); {len(RESOLVED)} variants "
        f"[{spiked}]; {n_pairs} read pairs at ~{args.coverage}x -> {args.outdir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
