import json
from pathlib import Path
from core.batch import list_images, run_batch
from core.integrity import sha256_file
from core.metadata import export_rows


def main():
    root = Path('data/Image2GPS25')
    paths = list_images(root / 'images')
    originals = paths + [root / 'metadata.csv']
    before = {str(p): sha256_file(p) for p in originals}
    result = run_batch(paths)
    unchanged = all(sha256_file(p) == before[str(p)] for p in originals)
    summary = {key: value for key, value in result.items() if key != 'rows'}
    summary.update(original_files_checked=len(originals), all_original_hashes_unchanged=unchanged,
                   all_internal_hashes_unchanged=all(r['hash_unchanged'] for r in result['rows']),
                   jpeg_structure_ok=sum(r.get('jpeg_structure', {}).get('structure_ok', False) for r in result['rows']))
    output = Path('outputs')
    output.mkdir(exist_ok=True)
    export_rows(result['rows'], output / 'stage3_batch_100.csv')
    keys = ('file', 'path', 'sha256_before', 'sha256_after', 'hash_unchanged', 'same_content_count', 'same_name_count')
    export_rows([{k: r.get(k) for k in keys} for r in result['rows']], output / 'stage3_sha256_100.csv')
    (output / 'stage3_validation.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    assert len(paths) == 100 and result['succeeded'] == 100 and result['failed'] == 0
    assert unchanged and summary['all_internal_hashes_unchanged']


if __name__ == '__main__':
    main()
