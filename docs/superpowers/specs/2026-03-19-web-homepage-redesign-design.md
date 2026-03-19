# Web Homepage Redesign Design

Date: 2026-03-19
Status: Approved in brainstorming
Scope: `/Users/Ditto/Documents/jingjipeixun/training_system/templates/index.html`, `/Users/Ditto/Documents/jingjipeixun/training_system/static/css/home.css`

## 1. Summary

Redesign the public web homepage for 阳泉精技特种作业人员培训有限公司 using the approved direction:

- Visual direction: 权威稳重
- Execution level: 结构升级

The redesign should keep the existing content model and main section set, but significantly improve first-screen clarity, trust signaling, visual hierarchy, and call-to-action strength. The page should feel like a credible local training institution website rather than a generic marketing template.

## 2. Goals

1. Build trust quickly in the first screen through a more official, grounded presentation.
2. Make the primary actions obvious: online application and phone consultation.
3. Reorder and restyle content so users can understand the institution, services, process, and contact path without scanning dense copy.
4. Preserve the current site architecture and routes while improving the homepage presentation.
5. Keep the page responsive and readable on mobile, including preserving the mobile bottom CTA bar.

## 3. Non-Goals

1. No backend changes.
2. No routing changes.
3. No CMS or dynamic news system.
4. No fabricated metrics or unverifiable business claims.
5. No redesign of `/apply`, `/login`, `/admin`, or the mini-program pages in this task.

## 4. Current Problems

The current homepage is structurally complete but visually too even. The main issues are:

1. The hero area introduces the business but does not establish trust and action priority strongly enough.
2. Section cards use a mostly uniform pattern, so the page lacks pacing and memorable hierarchy.
3. Important trust cues such as local service scope, compliance, training flow, and contact convenience are present but not emphasized enough.
4. The design language is respectable but still reads as a polished template rather than a distinct institutional homepage.

## 5. Chosen Design Direction

The page will remain in a deep blue and muted gold palette, but the redesign will make the system more controlled and institutional:

1. Deep blue remains the dominant trust color.
2. Gold becomes a restrained accent for premium and official cues.
3. Warm off-white and pale sand surfaces will be introduced to reduce the cold, generic look of blue-on-gray.
4. Typography and spacing will shift toward calmer authority instead of high-energy marketing.

This is not a full reinvention. It is a structured upgrade of the current homepage with a stronger narrative and clearer conversion path.

## 6. Information Architecture

The homepage will keep the current overall section set, with stronger prioritization:

1. Header / navigation
2. Hero
3. Trust highlights strip
4. About
5. Programs
6. Application guide
7. Teaching strength
8. News
9. Contact / closing CTA
10. Footer

Compared with the current page, the main change is that the top of the page will work harder:

1. The hero will directly state the institution type, value, and two primary actions.
2. A compact trust/highlight strip will sit immediately below the hero to reinforce credibility.
3. Mid-page sections will use more varied layouts so the page does not feel repetitive.

## 7. Section Design

### 7.1 Header

Keep the sticky header and main navigation, but refine presentation:

1. Tighten spacing and alignment to make the header feel more premium.
2. Preserve the current logo, company name, nav links, and `/apply` CTA.
3. Keep the semi-transparent dark backdrop, but make it slightly cleaner and less heavy.

### 7.2 Hero

The hero is the primary upgrade area.

Changes:

1. Reframe the hero copy so the first lines communicate trust and service scope more directly.
2. Keep two main CTAs: `立即报名` and `电话咨询`.
3. Replace the current side panel feel with a more integrated right-side information block composed of compact cards.
4. Use the right-side block to summarize:
   - institution trust/service highlights
   - simplified application flow
   - a contact shortcut
5. Preserve the current dark institutional mood, but create more contrast between the left content area and right support cards.

The hero should answer three questions at a glance:

1. What kind of institution is this?
2. What services can I get here?
3. What should I click next?

### 7.3 Trust Highlights Strip

Add or strengthen a slim highlight band immediately under the hero. This band should present short-value statements such as:

1. 阳泉本地服务
2. 培训 + 考证 + 复审
3. 企业安全培训
4. 规范教学流程

This strip exists to create fast scanning value on desktop and to reduce the perceived gap between hero and content sections.

### 7.4 About

Keep the current two-column structure concept, but reduce text wall effect:

1. Tighten paragraphs.
2. Turn the existing supporting trust cards into a more deliberate credibility grid.
3. Preserve the company positioning statement, but present it as a stronger emphasis block.

### 7.5 Programs

Retain the existing training program section, but improve card hierarchy:

1. Keep program cards as a grid.
2. Strengthen titles and spacing so the section reads more like a service catalog.
3. Ensure the cards do not visually blend into the surrounding sections.

### 7.6 Application Guide

This section should become clearer and more process-oriented.

Changes:

1. Keep the current four topics: conditions, materials, flow, cycle.
2. Style them more like a step-aware process block rather than generic cards.
3. Make `培训流程` especially easy to scan.

This is one of the highest-conversion sections because it reduces uncertainty before users contact the business.

### 7.7 Teaching Strength

Keep this section as the main proof block:

1. Preserve the darker background for contrast and pacing.
2. Keep the advantage cards, but make them feel more intentional and less repetitive.
3. Preserve the training environment subsection and its visual cards.
4. Increase the sense that this section demonstrates training seriousness, not just decoration.

### 7.8 News

Keep this section lightweight:

1. Preserve the current three-card structure.
2. Ensure it does not compete visually with the trust and guide sections.
3. It should support freshness and legitimacy, not dominate the page.

### 7.9 Contact / Closing CTA

This section should close the page more decisively.

1. Preserve the company name, location, contact person, and service range.
2. Strengthen the closing CTA card so the page ends with a clear next step.
3. Ensure both phone and online application actions remain immediately visible.

## 8. Responsive Behavior

The redesign must maintain full mobile usability.

Desktop:

1. Use a visually richer hero with a left-right composition.
2. Preserve enough whitespace to feel authoritative rather than crowded.

Tablet:

1. Collapse multi-column sections cleanly.
2. Keep CTAs visible without forcing excessive scrolling.

Mobile:

1. Re-stack the hero so the main copy appears before support cards.
2. Keep the bottom fixed CTA bar.
3. Reduce text density and card padding where needed.
4. Ensure important trust highlights remain visible early in the page.

## 9. Technical Implementation Notes

This redesign should primarily be implemented by editing the existing homepage template and stylesheet.

Expected file responsibility:

1. `/Users/Ditto/Documents/jingjipeixun/training_system/templates/index.html`
   - Adjust section markup where needed for improved structure and hierarchy.
   - Introduce any new hero support card markup and trust highlight strip markup.
2. `/Users/Ditto/Documents/jingjipeixun/training_system/static/css/home.css`
   - Redefine visual system variables if needed.
   - Update hero, cards, section spacing, and responsive rules.
   - Preserve current working behavior for floating and mobile actions.

JavaScript changes are not expected for this task unless minor presentational behavior is required.

## 10. Risks and Constraints

1. Overwriting too much structure would push this into a full redesign, which is out of scope.
2. Overusing gold accents would make the page feel decorative rather than authoritative.
3. Introducing fake metrics or unsupported proof points would reduce credibility.
4. Mobile hero density must be watched closely; the redesign should not create a crowded first screen on small devices.

## 11. Testing and Verification

Implementation should be verified with:

1. Visual review of desktop layout, especially hero hierarchy and CTA emphasis.
2. Visual review at tablet and mobile widths.
3. Anchor navigation sanity check.
4. CTA path sanity check for `/apply` and `tel:13703531055`.
5. Check that floating desktop actions and mobile fixed actions remain readable and do not overlap content incorrectly.

## 12. Definition of Done

The task is complete when:

1. The homepage clearly reflects the approved direction: 权威稳重 + 结构升级.
2. The hero communicates trust, service scope, and action path more clearly than the current version.
3. The page feels more distinctive and more official without adding unsupported claims.
4. Desktop and mobile layouts both remain polished and usable.
