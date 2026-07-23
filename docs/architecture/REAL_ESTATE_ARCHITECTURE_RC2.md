# Real-Estate Architecture RC2

RC2 extends RC1 with three controlled capabilities:

1. exact-address La Vanguardia zone evidence;
2. rights-gated Florence-2/LaMA media cleanup;
3. a header-aware Windows Excel COM plan for the `USANDO` workbook and an end-to-end AutoPPTX pipeline plan.

## Zone plane

The public repository does not scrape the La Vanguardia interactive. It creates a supervised capture plan and validates the resulting map screenshot, exact-address match, household income, legend bucket, source year and surroundings images.

Zone 1-5 thresholds are deliberately unset until the visible legend is captured, reviewed and versioned. Missing or conflicting evidence fails closed.

## Media plane

The WatermarkRemover-AI command contract is wrapped rather than copied. Cleanup is available only to owned, licensed, client-authorised or explicitly portal-authorised property media. The original is immutable; before/after hashes and an approval pointer are mandatory.

La Vanguardia, news-map, Street View and public map captures can never enter the cleanup path.

## Workbook and renderer plane

The Windows adapter:

- locates the `CODI` header;
- updates the existing project row or first empty row;
- writes values by header name;
- sets `#Pre-analisis!B3`;
- calls `CalculateFullRebuild`;
- saves and closes Excel;
- returns before/after workbook hashes.

The AutoPPTX pipeline binds the workbook plan, zone evidence, media-staging digest and existing four-role report job. It stages property and zone images using natural sorting and preserves all no-network/no-delivery boundaries.
