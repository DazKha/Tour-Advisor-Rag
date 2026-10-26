# Vietravel chatbot UI redesign

## Purpose and scope

Redesign the existing Streamlit chatbot for an interview demo. The interface should feel like a customer-facing travel consultation widget that could later be integrated into a website, while making the assistant's grounded answers and business judgment easy to inspect. Keep the current Streamlit deployment and the existing four-tour PDF corpus. This is a presentation and interaction redesign, not a booking flow or a change to the RAG architecture.

## Audience and success criteria

The primary viewer is an interviewer assessing both chatbot engineering and product judgment. A successful demo lets a new viewer start a relevant question quickly, understand which tour a follow-up concerns, read a concise answer, inspect its PDF support, and recognize when the assistant cannot confirm a fact. It must work on desktop and narrow mobile screens.

## Research basis

- Vietravel presents packaged tours through itineraries, experiences, and transparent service details: https://travel.com.vn/tours
- Baymard's travel-tour UX research covers discovery, evaluating tour details, and comparison: https://baymard.com/research/travel-tours-experience-booking
- Booking.com describes contextual Q&A as a way to help customers evaluate a travel option: https://news.booking.com/bookingcom-enhances-travel-planning-with-new-ai-powered-features--for-easier-smarter-decisions/

These sources inform interaction design only. The four supplied PDFs remain the sole factual authority for tour answers.

## Experience design

### Entry state

Show a compact branded header, one-sentence scope statement, and a prominent chat input. Provide four intent-based starting actions: itinerary, price and costs, tour comparison, and policies. Each action submits a concrete example question through the existing graph. Explain that the assistant covers four documented tours and that live availability and bookings require Vietravel staff. Keep this scope note concise so it does not dominate the screen.

### Conversation state

Keep chat as the main surface. Reduce the entry-state introduction after the first turn. Display the active tour or tours as small context labels derived from `active_tour_codes`; do not infer a tour from assistant prose. Offer follow-up prompts relevant to the active tour, while preserving free-text input. If no tour is active, use neutral prompts. The existing graph remains responsible for resolving references and asking clarifying questions.

Present each assistant message in this order: answer, status when attention is needed, and sources. Ordinary grounded answers should not carry a visually loud success banner. Source controls show tour name, section, and PDF page before revealing the excerpt. Technical citation metadata, including chunk IDs and retrieval scores, belongs in a separate demo-detail disclosure and does not appear as customer-facing copy.

For conflicting source claims, missing evidence, and requests for current availability or booking, visibly state the limitation and the next step. Never suggest that the assistant checked live inventory, changed a reservation, or confirmed a transaction. Preserve the answer text and citations returned by the graph; the UI must not generate new factual claims.

### Visual system and responsive behavior

Use a light, spacious layout with blue as the primary color and restrained orange accents inspired by Vietravel. Establish clear hierarchy for the brand/header, active tour context, answer text, citations, and secondary controls. Keep conversation text within a comfortable reading width. On narrow screens, stack suggested actions, avoid horizontal overflow, and keep the input easy to locate. Ensure controls have descriptive labels and visible keyboard focus.

The “Cuộc trò chuyện mới” control stays available without competing with the question input. It calls the existing reset behavior, including a new graph thread ID.

## Implementation boundaries

Keep `app.py` as the Streamlit entry point. Split UI rendering into focused helpers for the header/entry state, suggestions, context labels, message bodies, and source disclosures. Existing session state, `invoke_turn`, graph resources, citation allowlist, and error sanitization remain the source of behavior. Any tour label or prompt mapping must be deterministic and based on the reviewed catalog, not on invented prices, dates, or availability.

No website embedding, external assets, booking CTA, live inventory integration, new tour data, or changes to RAG prompts/retrieval are in this scope.

## Failure and empty states

If local data or provider configuration is unavailable, show the existing safe diagnostic message in the redesigned layout. If one turn fails, show a concise retryable error without exposing provider details or secrets. Empty chat remains useful through the four starter actions and free-text input. A clarification response should make the requested tour choice obvious in the answer and should not display an active-tour label unless the graph supplied one.

## Verification

Check desktop and narrow-screen rendering, starter and follow-up actions, a normal answer with PDF citation, an ambiguous-tour clarification, a documented conflict, a live-availability escalation, and conversation reset. Run existing relevant tests plus focused tests for any new pure presentation helpers. Verify that unchanged graph behavior still supplies citations and statuses and that source metadata remains allowlisted.
