# RC2 Handover

## Branch

`release/real-estate-architecture-rc2`

Base: `release/real-estate-architecture-rc1`

## Read first

1. `docs/manuals/REAL_ESTATE_GREATER_OPERATOR_MANUAL.md`
2. `docs/architecture/REAL_ESTATE_ARCHITECTURE_RC2.md`
3. `config/real-estate-zone-lavanguardia.json`
4. `config/real-estate-authorised-media-cleanup.json`
5. `config/real-estate-autopptx-rc2.json`
6. `intelligence/real_estate/zone_evidence.py`
7. `intelligence/real_estate/media_rights.py`
8. `intelligence/real_estate/autopptx_pipeline.py`
9. `scripts/windows_usando_excel_adapter.py`
10. `scripts/real_estate_rc2_cli.py`

## Current state

- La Vanguardia exact-address zone capture is supervised and evidence-bound.
- Map and surroundings images are hashed and attributed.
- Zone thresholds remain blocked until the actual legend is reviewed.
- Watermark cleanup is rights-gated and preserves the original.
- Map, news and Street View marks cannot be removed.
- USANDO workbook writes are header-aware and force full Excel recalculation.
- AutoPPTX planning binds workbook, zone, media and report-job digests.
- Real portal scraping, real CRM writes, report delivery and purchase actions remain blocked.

## Next private validation

1. Capture the actual La Vanguardia legend and approve the five buckets.
2. Test three real addresses manually against the map.
3. Configure the local WatermarkRemover entrypoint with authorised sample media.
4. Test the Excel COM adapter on a copied USANDO workbook.
5. Patch and configure the recovered AutoPPTX workspace.
6. Generate traditional, room and temporary golden reports.
7. Complete visual and financial checklist evidence.
