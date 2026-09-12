"""Compact presentation for the experimental habitat comparisons."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QTabWidget, QVBoxLayout, QWidget

from wildlocate.gui.formatting import feature_display
from wildlocate.gui.widgets import Disclosure, divider, label


def text(value, role='muted'):
    widget = label(value, role, True)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    return widget


def row(layout, title, detail, delta):
    container = QWidget()
    line = QHBoxLayout(container)
    line.setContentsMargins(0, 8, 0, 8)
    line.setSpacing(20)
    copy = QVBoxLayout()
    copy.setSpacing(4)
    copy.addWidget(text(title, 'fieldLabel'))
    copy.addWidget(text(detail, 'small'))
    line.addLayout(copy, 1)
    metric = text(f'{delta:+.3f}\nscore', 'fieldLabel')
    metric.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    metric.setStyleSheet('color: ' + ('#35664b' if delta > 0 else '#94523f' if delta < 0 else '#69776e') + ';')
    line.addWidget(metric)
    layout.addWidget(container)


class InsightsPanel(QWidget):
    def __init__(self, insights):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        if insights.get('error'):
            layout.addWidget(text(insights['error']))
            return
        tabs = QTabWidget()
        layout.addWidget(tabs)
        conditions = QWidget()
        body = QVBoxLayout(conditions)
        body.setContentsMargins(18, 18, 18, 18)
        body.setSpacing(8)
        body.addWidget(text('What’s shaping this score?', 'subheading'))
        body.addWidget(text('These conditions make the score higher or lower than it would be with typical values from other locations.'))
        influences = insights.get('influences', [])
        for heading, sign in [('BRINGING THE SCORE DOWN', -1), ('LIFTING THE SCORE UP', 1)]:
            body.addSpacing(12)
            body.addWidget(text(heading, 'step'))
            selected = sorted((item for item in influences if item['effect'] * sign > .0005),
                              key=lambda item: abs(item['effect']), reverse=True)[:2]
            if not selected:
                body.addWidget(text('Nothing stands out in this group.', 'small'))
            for item in selected:
                title, current = feature_display(item['feature'], item['current'])
                _, reference = feature_display(item['feature'], item['reference'])
                row(body, title, f'Here: {current}   ·   Typical: {reference}', item['effect'])
                body.addWidget(divider())
        body.addStretch()
        tabs.addTab(conditions, 'Local conditions')

        priorities_page = QWidget()
        body = QVBoxLayout(priorities_page)
        body.setContentsMargins(18, 18, 18, 18)
        body.setSpacing(12)
        species = insights.get('species', 'this species')
        body.addWidget(text(f'What matters most in the {species} model?', 'subheading'))
        body.addWidget(text('These are the model’s top three habitat features for this animal.'))
        priorities = insights.get('top_features', [])[:3]
        for rank, item in enumerate(priorities, 1):
            name = item['feature']
            current = insights.get('feature_values', {}).get(name, float('nan'))
            title, formatted = feature_display(name, current)
            card = QFrame()
            card.setObjectName('card')
            content = QHBoxLayout(card)
            content.setContentsMargins(14, 12, 14, 12)
            content.setSpacing(14)
            content.addWidget(text(f'{rank:02d}', 'subheading'))
            copy = QVBoxLayout()
            copy.setSpacing(4)
            copy.addWidget(text(title, 'fieldLabel'))
            description = f'Here: {formatted}'
            coefficient = item.get('coefficient')
            if coefficient is not None and coefficient != 0:
                direction = 'higher' if coefficient > 0 else 'lower'
                description += f' · Higher values tend to give {direction} scores in this model'
            copy.addWidget(text(description, 'small'))
            content.addLayout(copy, 1)
            body.addWidget(card)
        if not priorities:
            body.addWidget(text('This model doesn’t have a feature ranking to show yet.', 'small'))
        body.addStretch()
        tabs.addTab(priorities_page, 'Species priorities')
        layout.addWidget(text('These clues come from the model. They don’t prove what the animal needs or what would improve its habitat.', 'small'))
        method = Disclosure('How we work this out')
        method.body_layout.addWidget(text(
            'We rank features by how much the model relies on them. A feature near the top matters more to its predictions, but that doesn’t mean more of it is always better.\n\n'
            'To check a local condition, we replace it with the middle value from the training locations and leave everything else as it is. The number beside it shows how much higher or lower the original score is. '
            'These comparisons are separate, so their numbers won’t add up to the total score.', 'small'))
        layout.addWidget(method)
