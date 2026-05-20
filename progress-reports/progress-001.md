# Hexagamers.com Rebuild — Progress Report 001

**Date:** 2026-05-19  
**Status:** Planning complete, implementation starting

---

## Project Goal

Rebuild hexagamers.com from scratch — moving off WordPress/HostGator to a modern static site with free hosting. Maintain affiliate income (Amazon links, SEO) while getting a dramatically better design.

---

## Stack Decided

| Layer | Choice |
|-------|--------|
| Framework | Astro (static output, fast, SEO-friendly) |
| Hosting | GitHub Pages (free, auto-deploy via GitHub Actions) |
| Images | Cloudinary free tier — cloud name: `dt4ujaczs` |
| Design | frontend-design + ui-ux-pro-max skills (bold gaming aesthetic) |
| Domain | hexagamers.com (DNS migrated from HostGator → GitHub Pages) |

---

## Assets Collected

- [x] WordPress XML export → `/workspaces/projects/hexagamers/old-website/hexagamers.WordPress.2026-05-19.xml`
- [x] Cloudinary account created — cloud name: `dt4ujaczs`
- [x] Logo files → `/workspaces/projects/hexagamers/assets/`
  - `Hexgamers - H - No Background.png`
  - `Hexgamers Logo - No Background.png`

---

## Work Completed

- [x] Plan finalized and approved (saved to `/home/node/.claude/plans/`)
- [x] Stack selected: Astro + Cloudinary + GitHub Pages
- [x] Progress reports folder created

---

## Work Remaining

### Phase 1 — Scaffold Astro project
- [ ] `npm create astro@latest` in `/workspaces/projects/hexagamers/`
- [ ] Set up folder structure: pages, content, components, layouts, styles

### Phase 2 — Convert WordPress content
- [ ] Run `npx wordpress-export-to-markdown` on the XML export
- [ ] Output Markdown posts to `src/content/posts/`
- [ ] Update image URLs to point to Cloudinary CDN

### Phase 3 — Upload images to Cloudinary
- [ ] Download media from HostGator File Manager (zip + extract)
- [ ] Bulk upload to Cloudinary (`dt4ujaczs`)
- [ ] Collect CDN URLs for use in posts

### Phase 4 — Design & Build (frontend-design + ui-ux-pro-max skills)
- [ ] Aesthetic direction: dark base, hexagon motifs, sharp accent (teal or amber), editorial typography
- [ ] Homepage: hero, featured post, category nav, post grid
- [ ] Post page: clean readable layout, sidebar, affiliate disclosure
- [ ] Category pages: filtered post grids
- [ ] About page
- [ ] Mobile responsive, accessible (4.5:1 contrast, 44×44px touch targets)
- [ ] Staggered load animations, hover states on cards

### Phase 5 — GitHub Pages deployment
- [ ] Create GitHub repo
- [ ] Add `.github/workflows/deploy.yml` (push → build → deploy)
- [ ] Configure GitHub Pages to use GitHub Actions source
- [ ] Point hexagamers.com DNS to GitHub Pages (A records + CNAME)

---

## Key Notes

- WordPress XML is too large to read directly into the prompt — must use `npx wordpress-export-to-markdown` CLI
- Cloudinary replaces HostGator for all image hosting; no images stored in the GitHub repo
- All work is scoped to `/workspaces/projects/hexagamers/`
- Amazon affiliate links need `rel="nofollow"` and `target="_blank"`
- Lighthouse target: 90+ on Performance, SEO, Accessibility
