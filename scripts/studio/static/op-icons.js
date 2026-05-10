// Op icon registry — minimalist 24x24 line glyphs for every op.
// Stroke-based so they pick up `currentColor` and look crisp at any size.
// Categories also get their own icon.
//
// Each entry is the *inner* SVG content (paths/circles/etc); the renderer
// wraps it in <svg viewBox="0 0 24 24" stroke="currentColor" fill="none"
// stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">.

window.OP_ICONS = {
  // ---- Categories ---------------------------------------------------------
  _cat_transform: '<rect x="3" y="3" width="11" height="11" rx="1"/><path d="M14 14l7 7M14 21h7v-7"/>',
  _cat_filter:    '<path d="M4 5h16M7 12h10M11 19h2"/>',
  _cat_color:     '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 0 0 18 4.5 4.5 0 0 0 0-9 4.5 4.5 0 0 1 0-9z"/>',
  _cat_effect:    '<path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/><circle cx="12" cy="12" r="3"/>',
  _cat_compose:   '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 16h18M8 16v5"/>',
  _cat_social:    '<rect x="3" y="3" width="18" height="18" rx="4"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="0.5" fill="currentColor"/>',
  _cat_gif:       '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M7 10v4M7 12h2M11 10v4M14 10h3M14 14h3M14 12h2"/>',
  _cat_animate:   '<circle cx="12" cy="12" r="9"/><path d="M10 9l5 3-5 3z" fill="currentColor"/>',
  _cat_utility:   '<path d="M14.7 6.3a4 4 0 0 0-5.6 5.6l-6 6 2.1 2.1 6-6a4 4 0 0 0 5.6-5.6l-2.5 2.5-2.1-2.1z"/>',

  // ---- transform ----------------------------------------------------------
  resize:          '<rect x="4" y="4" width="11" height="11" rx="1"/><path d="M15 9h5v5M20 9l-5 5"/>',
  crop:            '<path d="M6 3v15h15M3 6h15v15"/>',
  rotate:          '<path d="M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5"/>',
  flip:            '<path d="M12 3v18M7 7l-3 5 3 5zM17 7l3 5-3 5z"/>',
  mirror:          '<path d="M12 3v18M4 8l5 4-5 4zM20 8l-5 4 5 4z"/>',
  upscale:         '<path d="M4 14l4-4 3 3 4-4 5 5M4 4h6M4 4v6"/>',
  thumbnail:       '<rect x="3" y="3" width="18" height="18" rx="2"/><rect x="7" y="7" width="10" height="10" rx="1"/>',
  fix_orientation: '<rect x="6" y="3" width="12" height="18" rx="2"/><path d="M9 8h6M12 8v8M9 16l3 3 3-3"/>',

  // ---- filter -------------------------------------------------------------
  blur:         '<circle cx="8" cy="8" r="3" opacity="0.3"/><circle cx="14" cy="14" r="4" opacity="0.6"/><circle cx="12" cy="12" r="6" opacity="0.2"/>',
  cartoon:      '<circle cx="9" cy="10" r="1.2"/><circle cx="15" cy="10" r="1.2"/><path d="M8 15c1.5 1.5 6.5 1.5 8 0"/><circle cx="12" cy="12" r="9"/>',
  deep_fry:     '<circle cx="12" cy="12" r="9"/><path d="M12 6v3M12 15v3M6 12h3M15 12h3M8 8l2 2M14 14l2 2M8 16l2-2M14 10l2-2"/>',
  duotone:      '<circle cx="9" cy="12" r="6"/><circle cx="15" cy="12" r="6" opacity="0.6"/>',
  edge:         '<path d="M3 21l6-6 4 4 8-8"/><path d="M3 12l4-4 5 5 9-9" opacity="0.4"/>',
  emboss:       '<path d="M5 19l7-14 7 14"/><path d="M5 19l7-7 7 7" opacity="0.5"/>',
  glitch:       '<path d="M5 7h8M11 11h10M3 15h13M9 19h11" stroke-width="2"/>',
  glow:         '<circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="6" opacity="0.5"/><circle cx="12" cy="12" r="9" opacity="0.2"/>',
  grayscale:    '<circle cx="12" cy="12" r="9"/><path d="M12 3v18"/>',
  halftone:     '<circle cx="6" cy="6" r="1.5" fill="currentColor"/><circle cx="12" cy="6" r="1.2" fill="currentColor"/><circle cx="18" cy="6" r="0.8" fill="currentColor"/><circle cx="6" cy="12" r="1.2" fill="currentColor"/><circle cx="12" cy="12" r="0.8" fill="currentColor"/><circle cx="18" cy="12" r="0.5" fill="currentColor"/><circle cx="6" cy="18" r="0.8" fill="currentColor"/><circle cx="12" cy="18" r="0.5" fill="currentColor"/><circle cx="18" cy="18" r="0.3" fill="currentColor"/>',
  invert:       '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/>',
  oil_painting: '<path d="M5 18c2-3 3-5 5-5s2 4 5 4 4-3 4-3M5 13c2-2 3-3 5-3s2 2 5 2 4-2 4-2"/>',
  pencil_sketch:'<path d="M4 20l9-9 4 4-9 9zM13 11l3-3 4 4-3 3z"/>',
  pixelate:     '<rect x="4" y="4" width="4" height="4"/><rect x="10" y="4" width="4" height="4"/><rect x="16" y="4" width="4" height="4"/><rect x="4" y="10" width="4" height="4"/><rect x="10" y="10" width="4" height="4"/><rect x="16" y="10" width="4" height="4"/><rect x="4" y="16" width="4" height="4"/><rect x="10" y="16" width="4" height="4"/><rect x="16" y="16" width="4" height="4"/>',
  posterize:    '<path d="M3 6h18M3 12h18M3 18h18" stroke-width="2.5"/>',
  scanlines:    '<path d="M3 6h18M3 9h18M3 12h18M3 15h18M3 18h18"/>',
  sepia:        '<circle cx="12" cy="12" r="9"/><path d="M9 9c2-1 4-1 6 0M9 15c2 1 4 1 6 0"/>',
  sharpen:      '<path d="M12 3l9 18H3z"/>',
  solarize:     '<circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"/>',
  vaporwave:    '<path d="M3 18l9-12 9 12M3 14l9-8 9 8M3 21h18"/>',
  vignette:     '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="12" cy="12" r="5"/>',

  // ---- color --------------------------------------------------------------
  auto_contrast: '<circle cx="12" cy="12" r="9"/><path d="M12 3v18" /><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/>',
  auto_level:    '<path d="M3 18l4-6 4 3 4-9 6 12"/><path d="M3 21h18"/>',
  brightness:    '<circle cx="12" cy="12" r="3.5"/><path d="M12 4v2M12 18v2M4 12h2M18 12h2M6.3 6.3l1.4 1.4M16.3 16.3l1.4 1.4M6.3 17.7l1.4-1.4M16.3 7.7l1.4-1.4"/>',
  contrast:      '<circle cx="12" cy="12" r="9"/><path d="M12 3v18" /><path d="M12 21a9 9 0 0 1 0-18z" fill="currentColor"/>',
  saturation:    '<path d="M12 3c-4 5-7 8-7 12a7 7 0 0 0 14 0c0-4-3-7-7-12z"/>',

  // ---- effect -------------------------------------------------------------
  bg_color:    '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 14l5-5 4 4 5-5 4 4"/>',
  border:      '<rect x="3" y="3" width="18" height="18" rx="1" stroke-width="2.5"/><rect x="8" y="8" width="8" height="8" stroke-dasharray="2 2"/>',
  drop_shadow: '<rect x="4" y="3" width="13" height="13" rx="1"/><rect x="7" y="6" width="13" height="13" rx="1" opacity="0.4" fill="currentColor" stroke="none"/>',
  round_corners:'<path d="M3 11V7a4 4 0 0 1 4-4h4M21 13v4a4 4 0 0 1-4 4h-4M3 13v4a4 4 0 0 0 4 4h4M21 11V7a4 4 0 0 0-4-4h-4"/>',
  vectorize:   '<path d="M5 19l7-14 7 14z"/><circle cx="12" cy="5" r="1.5" fill="currentColor"/><circle cx="5" cy="19" r="1.5" fill="currentColor"/><circle cx="19" cy="19" r="1.5" fill="currentColor"/>',
  watermark:   '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M14 16h4M14 19h4"/>',

  // ---- compose ------------------------------------------------------------
  annotate:      '<rect x="3" y="3" width="18" height="14" rx="2"/><path d="M9 21l3-4 3 4M7 9h10M7 12h6"/>',
  caption_top:   '<path d="M3 3h18v5H3z" fill="currentColor" stroke="none" opacity="0.4"/><rect x="3" y="3" width="18" height="18" rx="1"/><path d="M7 6h10"/>',
  meme:          '<rect x="3" y="3" width="18" height="18" rx="1"/><path d="M6 7h12M6 18h12" stroke-width="2"/>',
  polaroid:      '<rect x="4" y="3" width="16" height="18" rx="1"/><rect x="6" y="5" width="12" height="11"/><path d="M9 19h6"/>',
  thought_bubble:'<path d="M9 4h7a4 4 0 0 1 0 8h-1l-3 3v-3h-3a4 4 0 0 1 0-8z"/><circle cx="6" cy="17" r="1.5"/><circle cx="3.5" cy="20" r="0.8"/>',

  // ---- social -------------------------------------------------------------
  ig_portrait:   '<rect x="6" y="2" width="12" height="20" rx="2"/><circle cx="12" cy="12" r="3"/><circle cx="15.5" cy="6" r="0.5" fill="currentColor"/>',
  ig_square:     '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="12" cy="12" r="4"/><circle cx="17" cy="7" r="0.6" fill="currentColor"/>',
  ig_story:      '<rect x="6" y="2" width="12" height="20" rx="3"/><path d="M9 7h6M10 17h4"/>',
  twitter_header:'<rect x="2" y="7" width="20" height="10" rx="1"/><path d="M7 11l3 2-3 2M14 11h3M14 14h3"/>',
  yt_thumbnail:  '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M10 9l5 3-5 3z" fill="currentColor"/>',

  // ---- gif ----------------------------------------------------------------
  gif_boomerang:'<path d="M5 12c0-3 7-3 7 0s7 3 7 0"/><path d="M19 12l-2-2M19 12l-2 2"/>',
  gif_caption:  '<rect x="3" y="6" width="18" height="12" rx="1"/><path d="M6 9h12M6 15h12" stroke-width="2"/>',
  gif_filter:   '<rect x="3" y="6" width="18" height="12" rx="1"/><path d="M9 9l6 6M15 9l-6 6"/>',
  gif_optimize: '<rect x="3" y="6" width="18" height="12" rx="1"/><path d="M8 12l3 3 5-6"/>',
  gif_resize:   '<rect x="3" y="6" width="18" height="12" rx="1"/><path d="M14 9h4v4M18 9l-4 4M10 15H6v-4M6 15l4-4"/>',
  gif_reverse:  '<rect x="3" y="6" width="18" height="12" rx="1"/><path d="M16 12l-5-3v6zM10 12l-3-2v4z"/>',
  gif_speed:    '<rect x="3" y="6" width="18" height="12" rx="1"/><path d="M10 9l5 3-5 3zM6 9l3 3-3 3z"/>',

  // ---- animate ------------------------------------------------------------
  animate_drift:     '<path d="M5 12c2-3 4-3 7 0s5 3 7 0"/><path d="M5 17c2-3 4-3 7 0s5 3 7 0" opacity="0.5"/>',
  animate_flicker:   '<path d="M12 3c-1 4 3 4 3 8s-3 5-3 10c-3-2-4-5-4-7s2-4 1-7c1 1 3 1 3-4z"/>',
  animate_fog:       '<path d="M4 9c2-1 6-1 8 0s6 1 8 0M4 13c2-1 6-1 8 0s6 1 8 0M4 17c2-1 6-1 8 0s6 1 8 0" opacity="0.7"/>',
  animate_glow_pulse:'<circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="6" opacity="0.5"/><circle cx="12" cy="12" r="9" opacity="0.2"/>',
  animate_ken_burns: '<rect x="3" y="3" width="18" height="14" rx="1"/><rect x="6" y="6" width="12" height="9" stroke-dasharray="2 2"/><path d="M8 8l-3-3M16 8l3-3"/>',
  animate_lightning: '<path d="M13 3l-7 11h5l-2 7 7-11h-5z" fill="currentColor" stroke="none"/>',
  animate_pan:       '<rect x="3" y="6" width="18" height="12" rx="1"/><path d="M7 12h10M14 9l3 3-3 3"/>',
  animate_particles: '<circle cx="6" cy="6" r="1" fill="currentColor"/><circle cx="13" cy="9" r="0.8" fill="currentColor"/><circle cx="9" cy="14" r="1.2" fill="currentColor"/><circle cx="17" cy="13" r="0.6" fill="currentColor"/><circle cx="15" cy="18" r="1" fill="currentColor"/><circle cx="6" cy="18" r="0.7" fill="currentColor"/><circle cx="19" cy="6" r="0.7" fill="currentColor"/>',
  animate_pulse:     '<path d="M3 12h4l2-6 4 12 2-6h6"/>',
  animate_ripple:    '<path d="M3 10c2-2 4-2 6 0s4 2 6 0 4-2 6 0M3 16c2-2 4-2 6 0s4 2 6 0 4-2 6 0"/>',
  animate_rotate:    '<path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v5h-5"/>',
  animate_shake:     '<path d="M5 8l3 4-3 4M19 8l-3 4 3 4M9 6l3 4-3 4 3 4M15 6l-3 4 3 4-3 4"/>',
  animate_shimmer:   '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 17l10-10" stroke-width="3"/>',
  animate_sway:      '<path d="M12 4v8M8 16c0-2 2-3 4-4s4 2 4 4" /><circle cx="12" cy="4" r="1.5"/>',
  animate_zoom:      '<rect x="3" y="3" width="18" height="18" rx="1"/><rect x="7" y="7" width="10" height="10"/><rect x="10" y="10" width="4" height="4" fill="currentColor"/>',

  // ---- utility ------------------------------------------------------------
  compress:      '<path d="M5 7l4 4-4 4M19 7l-4 4 4 4M9 11h6M9 13h6"/>',
  convert:       '<path d="M4 7h11l-3-3M20 17H9l3 3"/>',
  remove_bg:     '<rect x="3" y="3" width="18" height="18" rx="2" stroke-dasharray="3 2"/><circle cx="12" cy="11" r="3"/><path d="M6 19c1-3 4-4 6-4s5 1 6 4"/>',
  strip_metadata:'<rect x="5" y="3" width="14" height="18" rx="1"/><path d="M9 8h6M9 12h6M9 16h3"/><path d="M4 4l16 16" stroke-width="2"/>',

  // Default fallback
  _default: '<circle cx="12" cy="12" r="9"/>',
};

// Category metadata: pretty label + accent color hint (used as fallback when
// the user hasn't picked an accent override). Lifted from a Figma-ish palette.
window.OP_CATEGORIES = {
  transform: { label: "Transform", hue: 200 },
  filter:    { label: "Filter",    hue: 280 },
  color:     { label: "Color",     hue:  20 },
  effect:    { label: "Effect",    hue: 160 },
  compose:   { label: "Compose",   hue: 340 },
  social:    { label: "Social",    hue: 220 },
  gif:       { label: "GIF",       hue:  50 },
  animate:   { label: "Animate",   hue: 300 },
  utility:   { label: "Utility",   hue: 110 },
};

window.renderOpIcon = function(name, size = 18) {
  const inner = window.OP_ICONS[name] || window.OP_ICONS._default;
  return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`;
};
