# Local Visual Brief Fallback

Concept type: model_shoot
Use case: New model/product visual concept

## Image Prompt
Test model image generation path after fallback fix.

Use design sources as final product truth. Use blank fit model sources only for pose, fit, silhouette, drape, crop, neckline, sleeve shape, and material behavior. Do not output the blank garment when a designed product source exists.

Design sources: Essential Wide Neck Baby T-shirt-mockups-1.png, Essential Wide Neck Baby T-shirt-mockups-2.png
Fit/model sources: Essential Wide Neck Baby T-shirt-mockups-6.png, Essential Wide Neck Baby T-shirt-mockups-7.png, Essential Wide Neck Baby T-shirt-mockups-8.png, Essential Wide Neck Baby T-shirt-mockups-9.png
Material/detail sources: Essential Wide Neck Baby T-shirt-mockups-3.png, Essential Wide Neck Baby T-shirt-mockups-4.png, Essential Wide Neck Baby T-shirt-mockups-5.png

## Product Placement Requirements
Product: Essential Wide Neck Baby T Shirt
Garment type: t-shirt
Silhouette: t-shirt, wide neck
Fabric/wash: match product references
Front graphic policy: use_front_design
Back graphic policy: use_back_design
Design sources: Essential Wide Neck Baby T-shirt-mockups-1.png, Essential Wide Neck Baby T-shirt-mockups-2.png
Fit/model sources: Essential Wide Neck Baby T-shirt-mockups-6.png, Essential Wide Neck Baby T-shirt-mockups-7.png, Essential Wide Neck Baby T-shirt-mockups-8.png, Essential Wide Neck Baby T-shirt-mockups-9.png
Material/detail sources: Essential Wide Neck Baby T-shirt-mockups-3.png, Essential Wide Neck Baby T-shirt-mockups-4.png, Essential Wide Neck Baby T-shirt-mockups-5.png
Use blank_fit_model references only for pose, fit, silhouette, drape, crop, neckline, sleeve shape, and fabric behavior. Do not treat blank model shots as the final product design.
Use front_design/back_design references as the source of truth for actual sellable product graphics, logos, artwork, and placement.
Front requirements: For front-facing renders, use front_design references as the source of truth for actual sellable product artwork, logo, graphic placement, and product color.; Use blank_fit_model references only for fit/silhouette/material behavior. Do not let blank model shots erase actual product artwork.
Back requirements: For back-facing renders, use back_design references as the source of truth for actual sellable product artwork and placement.; Do not move back artwork onto the front of the garment.
Detail requirements: Preserve visible trims, tags, hems, grommets, neck shape, sleeve/arm opening, fabric texture, and wash.
Must never omit: side-specific branding/graphic placement; garment silhouette; fabric color/wash
Must not invent: readable fake text; new brand names; new garment graphics not shown in the product folder; moving back graphics onto the front; removing visible front marks/logos when front references show them
Front refs: Essential Wide Neck Baby T-shirt-mockups-1.png
Back refs: Essential Wide Neck Baby T-shirt-mockups-2.png
Detail refs: Essential Wide Neck Baby T-shirt-mockups-3.png, Essential Wide Neck Baby T-shirt-mockups-4.png, Essential Wide Neck Baby T-shirt-mockups-5.png

## Negative Prompt
No invented products, no fake readable text, no blank garment as final output when design sources exist, no back graphic moved to front, no missing front/back graphic placement.

## Brief Fallback Note
The agent brief call failed, so this deterministic local brief was used instead. Error: Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, read the docs: https://platform.openai.com/docs/guides/error-codes/api-errors.', 'type': 'insufficient_quota', 'param': None, 'code': 'insufficient_quota'}}
