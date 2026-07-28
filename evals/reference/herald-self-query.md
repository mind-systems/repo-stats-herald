The most recent work has been about getting releases out. Three things landed in sequence.

A release note is now scoped to the accumulation since the last deployment to a given environment, rather than to a fixed period — so a release describes exactly what that deployment carries, however long it has been since the previous one.

The note itself stopped being a separate mechanism. It is assembled by the same reporting engine that produces every other summary, so a release note and a routine report share one path rather than drifting apart.

Delivery closed the loop. A push to a release branch now cuts a GitHub release carrying the note, and the accompanying Telegram message leads with the version number. Before this, the version and the note existed but reached no release channel.
