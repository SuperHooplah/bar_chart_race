import pytest
import bar_chart_race._utils as utils
from bar_chart_race import load_dataset, bar_chart_race

df = load_dataset('baseball')
df = df.iloc[-20:-16]


def test_threshold():
    filt_df = utils.filter_threshold(df, 25)

    assert filt_df[filt_df.iloc[:, -1]] > 25
