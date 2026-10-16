# Hand photos (optional)

Drop photo cutouts here to replace the vector placeholder hands:

- `marker.png` — a hand holding a marker, photographed from above on white, background removed (transparent PNG).
- `pinch.png`  — a hand pinching (thumb + index together), same setup.

Then describe where the "working point" is in each image, in image pixels, in `hands.json`:

```json
{
  "marker": { "src": "marker.png", "tip":   [112, 38],  "width": 520 },
  "pinch":  { "src": "pinch.png",  "tip":   [60, 70],   "width": 520 }
}
```

`tip` = pixel of the marker tip / pinch point; `width` = how wide the hand should appear on the 1280x720 canvas.
The hand should extend down-right from that point (a right hand entering from the bottom-right corner).
If `hands.json` is missing the renderer uses the built-in vector hands from `lib/parts.svg`.
