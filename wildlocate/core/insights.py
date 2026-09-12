"""Experimental model sensitivity; these comparisons are not causal effects."""
import numpy as np


def habitat_insights(model, frame, comparison, comparison_scores, score):
    def evaluate(candidate):
        value = float(model.predict_proba(candidate)[0, 1])
        if not np.isfinite(value):
            raise ValueError('Non-finite scenario prediction')
        return value, int(round(100 * np.mean(comparison_scores < value)))

    influences = []
    for name in frame.columns:
        values = comparison[name].replace([np.inf, -np.inf], np.nan).dropna()
        if values.empty:
            continue
        reference = float(values.median())
        candidate = frame.copy()
        candidate.loc[:, name] = reference
        alternative, _ = evaluate(candidate)
        influences.append({'feature': name, 'current': float(frame.iloc[0][name]),
                           'reference': reference, 'effect': score - alternative})
    influences.sort(key=lambda item: abs(item['effect']), reverse=True)

    scenarios = []
    tested = 0
    baseline_percentile = int(round(100 * np.mean(comparison_scores < score)))
    # Search a small, explicit grid; retain the strongest visible gain per
    # scenario type. These are model experiments, not an intervention optimizer.
    for kind in ('forest', 'impervious'):
        best = None
        for fraction in (.1, .25, .5):
            candidate = frame.copy()
            changes = []
            for radius in ('250m', '1000m'):
                if kind == 'forest':
                    source, target = f'developed_fraction_{radius}', f'forest_fraction_{radius}'
                    if source not in frame or target not in frame:
                        continue
                    amount = min(float(frame.iloc[0][source]) * fraction,
                                 1 - float(frame.iloc[0][target]))
                    updates = {source: float(frame.iloc[0][source]) - amount,
                               target: float(frame.iloc[0][target]) + amount}
                else:
                    source = f'mean_impervious_{radius}'
                    if source not in frame:
                        continue
                    updates = {source: float(frame.iloc[0][source]) * (1 - fraction)}
                for name, value in updates.items():
                    before = float(frame.iloc[0][name])
                    if abs(value - before) > 1e-10:
                        candidate.loc[:, name] = value
                        changes.append({'feature': name, 'before': before, 'after': value})
            if not changes:
                continue
            tested += 1
            value, percentile = evaluate(candidate)
            delta = value - score
            if delta < .001 or (best is not None and delta <= best['delta'] + 1e-10):
                continue
            percent = int(fraction * 100)
            title = (f'Replace {percent}% of developed cover with forest' if kind == 'forest'
                     else f'Reduce impervious surface by {percent}%')
            best = {'title': title, 'score': value, 'delta': delta,
                    'percentile': percentile, 'changes': changes}
        if best is not None:
            scenarios.append(best)
    scenarios.sort(key=lambda item: item['delta'], reverse=True)
    return {'influences': influences, 'scenarios': scenarios,
            'baseline_score': float(score), 'baseline_percentile': baseline_percentile,
            'scenarios_tested': tested}
