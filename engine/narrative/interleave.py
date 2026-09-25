"""Interleave discovered story arcs without flattening them into one plot."""

from __future__ import annotations

from collections import defaultdict

from .models import ArcInterleaveSlot, NarrativeSequence, StoryArc


class MultiArcInterleaver:
    def plan(self, arcs:list[StoryArc], sequences:list[NarrativeSequence], max_consecutive:int=2) -> list[ArcInterleaveSlot]:
        if not arcs or not sequences:
            return []
        seq_by_id={sequence.id:sequence for sequence in sequences}
        remaining=[]
        for arc in arcs:
            for sequence_id in arc.sequence_ids:
                sequence=seq_by_id.get(sequence_id)
                if sequence is not None:
                    remaining.append((arc,sequence))
        buckets=defaultdict(list)
        for arc,sequence in remaining:
            buckets[arc.id].append((arc,sequence))
        last_arc=None
        consecutive=0
        result=[]
        rank=1
        while any(buckets.values()):
            candidates=[]
            for arc_id,items in buckets.items():
                if not items: continue
                if arc_id==last_arc and consecutive>=max_consecutive: continue
                arc,sequence=items[0]
                candidates.append((arc,sequence))
            if not candidates:
                candidates=[items[0] for items in buckets.values() if items]
            candidates.sort(key=lambda pair:(-pair[0].tension,-pair[0].completion_signal,pair[0].id))
            arc,sequence=candidates[0]
            buckets[arc.id].pop(0)
            reason=("continue current arc" if arc.id==last_arc else "switch arc to preserve multi-line tension")
            result.append(ArcInterleaveSlot(arc.id,sequence.id,rank,reason))
            if arc.id==last_arc: consecutive+=1
            else: last_arc=arc.id; consecutive=1
            rank+=1
        return result
