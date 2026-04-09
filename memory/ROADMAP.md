# Audioraq Roadmap

## Outcome
Turn Audioraq from a working prototype into a podcast platform with:
- better listener activation
- stronger repeat listening loops
- creator workflows that feel like running a show

## Release Plan
### Release A - Product Foundation
- show vs episode data model
- listener dashboard becomes home feed
- browse becomes exploration
- episode detail page
- listener settings
- podcaster settings
- onboarding progress and stronger defaults

### Release B - Discovery And Quality
- public browse for logged-out visitors
- search filters for duration, media type, and sort
- recommendation explanation labels
- feedback actions: save, follow, not interested
- better empty states
- trust signals and creator/show quality markers

### Release C - Listening Retention
- continue listening rail
- listening history page
- queue and play next
- saved episodes and lightweight collections
- follows and new episode updates

### Release D - Creator Workflow
- show setup flow
- first-upload concierge
- draft vs publish
- post-publish editing
- creator analytics
- RSS import

## Engineering Sequence
1. Add show and episode collections plus migration strategy
2. Introduce route structure for:
- show page
- episode detail page
- creator settings
- listener settings
3. Add interaction event model:
- impression
- started
- 30 seconds listened
- 50 percent completed
- saved
- followed
- skipped
- not interested
4. Rebuild recommendation ranking on top of stronger signals
5. Rebuild creator dashboard on top of the show model

## Design Notes
- Dashboard should answer "what should I listen to next?"
- Browse should answer "what exists here?"
- Episode page should answer "should I commit to this?"
- Creator studio should answer "what should I publish or improve next?"

## Success Criteria
- visitors can sample content before signup
- new listeners reach first meaningful play faster
- creators can launch a show, not just upload a file
- recommendations get better as behavior accumulates
- listeners have reasons to return beyond one-off search
