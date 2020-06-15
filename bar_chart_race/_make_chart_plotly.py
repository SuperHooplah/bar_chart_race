import numpy as np
import pandas as pd
import bar_chart_race as bcr
import plotly.graph_objects as go
import plotly


from ._make_chart import prepare_wide_data


class _BarChartRace:
    
    def __init__(self, df, filename, orientation, sort, n_bars, fixed_order, fixed_max,
                 steps_per_period, period_length, interpolate_period, label_bars, bar_size, 
                 period_label, period_fmt, period_summary_func, perpendicular_bar_func, figsize, 
                 cmap, title, title_size, bar_label_size, tick_label_size, shared_fontdict, scale, 
                 fig, dpi, bar_kwargs, filter_column_colors):
        self.filename = filename
        self.extension = self.get_extension()
        self.orientation = orientation
        self.sort = sort
        self.n_bars = n_bars or df.shape[1]
        self.fixed_order = fixed_order
        self.fixed_max = fixed_max
        self.steps_per_period = steps_per_period
        self.interpolate_period = interpolate_period
        self.label_bars = label_bars
        self.bar_size = bar_size
        self.period_label = self.get_period_label(period_label)
        self.period_fmt = period_fmt
        self.period_summary_func = period_summary_func
        self.perpendicular_bar_func = perpendicular_bar_func
        self.period_length = period_length
        self.figsize = figsize
        self.title = title
        self.title_size = title_size
        self.bar_label_size = bar_label_size
        self.tick_label_size = tick_label_size
        self.scale = scale
        self.fps = 1000 / self.period_length * steps_per_period
        self.filter_column_colors = filter_column_colors
        
        self.validate_params()
        self.bar_kwargs = self.get_bar_kwargs(bar_kwargs)
        self.html = self.filename is None
        self.df_values, self.df_ranks = self.prepare_data(df)
        self.col_filt = self.get_col_filt()
        self.bar_colors = self.get_bar_colors(cmap)
        self.set_xy_limits()
        self.str_index = self.df_values.index.astype('str')
        

    def get_extension(self):
        if self.filename:
            return self.filename.split('.')[-1]

    def validate_params(self):
        if isinstance(self.filename, str):
            if '.' not in self.filename:
                raise ValueError('`filename` must have an extension')
        elif self.filename is not None:
            raise TypeError('`filename` must be None or a string')
            
        if self.sort not in ('asc', 'desc'):
            raise ValueError('`sort` must be "asc" or "desc"')

        if self.orientation not in ('h', 'v'):
            raise ValueError('`orientation` must be "h" or "v"')

    def get_bar_kwargs(self, bar_kwargs):
        bar_kwargs = bar_kwargs or {}
        if 'width' in bar_kwargs or 'height' in bar_kwargs:
            raise ValueError("Do not set the width or height with `bar_kwargs`. "
                             "Instead, use `bar_size`.")
        if self.orientation == 'h':
            bar_kwargs['height'] = self.bar_size
        else:
            bar_kwargs['width'] = self.bar_size
        if 'alpha' not in bar_kwargs:
            bar_kwargs['alpha'] = .8
        if 'ec' not in bar_kwargs:
            bar_kwargs['ec'] = 'white'
        return bar_kwargs

    def get_period_label(self, period_label):
        if not period_label:
            return False
        elif period_label is True:
            period_label = {'size': 12}
            if self.orientation == 'h':
                period_label['x'] = .95
                period_label['y'] = .15 if self.sort == 'desc' else .85
                period_label['ha'] = 'right'
                period_label['va'] = 'center'
            else:
                period_label['x'] = .95 if self.sort == 'desc' else .05
                period_label['y'] = .85
                period_label['ha'] = 'right' if self.sort == 'desc' else 'left'
                period_label['va'] = 'center'
        else:
            if 'x' not in period_label or 'y' not in period_label:
                raise ValueError('`period_label` dictionary must have keys for "x" and "y"')
        return period_label

    def prepare_data(self, df):
        if self.fixed_order is True:
            last_values = df.iloc[-1].sort_values(ascending=False)
            cols = last_values.iloc[:self.n_bars].index
            df = df[cols]
        elif isinstance(self.fixed_order, list):
            cols = self.fixed_order
            df = df[cols]
            self.n_bars = min(len(cols), self.n_bars)
            
        compute_ranks = self.fixed_order is False
        dfs = prepare_wide_data(df, self.orientation, self.sort, self.n_bars,
                                self.interpolate_period, self.steps_per_period,
                                compute_ranks)
        if isinstance(dfs, tuple):
            df_values, df_ranks = dfs
        else:
            df_values = dfs

        if self.fixed_order:
            n = df_values.shape[1] + 1
            m = df_values.shape[0]
            rank_row = np.arange(1, n)
            if (self.sort == 'desc' and self.orientation == 'h') or \
                (self.sort == 'asc' and self.orientation == 'v'):
                rank_row = rank_row[::-1]
            
            ranks_arr = np.repeat(rank_row.reshape(1, -1), m, axis=0)
            df_ranks = pd.DataFrame(data=ranks_arr, columns=cols)

        return df_values, df_ranks

    def get_col_filt(self):
        col_filt = pd.Series([True] * self.df_values.shape[1])
        if self.n_bars < self.df_ranks.shape[1]:
            orient_sort = self.orientation, self.sort
            if orient_sort in [('h', 'asc'), ('v', 'desc')]:
                # 1 is high
                col_filt = (self.df_ranks < self.n_bars + .99).any()
            else:
                # 1 is low
                col_filt = (self.df_ranks > 0).any()

            if self.filter_column_colors and not col_filt.all():
                self.df_values = self.df_values.loc[:, col_filt]
                self.df_ranks = self.df_ranks.loc[:, col_filt]
        return col_filt
        
    def get_bar_colors(self, cmap):
        if cmap is None:
            cmap = 'dark12'
            if self.df_values.shape[1] > 12:
                cmap = 'dark24'
            
        if isinstance(cmap, str):
            from ._colormaps import colormaps
            try:
                bar_colors = colormaps[cmap.lower()]
            except KeyError:
                raise KeyError(f'Colormap {cmap} does not exist. Here are the '
                               f'possible colormaps: {colormaps.keys()}')
        elif isinstance(cmap, colors.Colormap):
            bar_colors = cmap(range(cmap.N)).tolist()
        elif isinstance(cmap, list):
            bar_colors = cmap
        elif isinstance(cmap, tuple):
            bar_colors = list(cmap)
        elif hasattr(cmap, 'tolist'):
            bar_colors = cmap.tolist()
        else:
            raise TypeError('`cmap` must be a string name of a colormap, a matplotlib colormap '
                            'instance, list, or tuple of colors')

        # bar_colors is now a list
        n = len(bar_colors)
        orig_bar_colors = bar_colors
        if self.df_values.shape[1] > n:
            bar_colors = bar_colors * (self.df_values.shape[1] // n + 1)
        bar_colors = np.array(bar_colors[:self.df_values.shape[1]])

        if not self.filter_column_colors:
            if not self.col_filt.all():
                col_idx = np.where(self.col_filt)[0] % n
                col_idx_ct = np.bincount(col_idx, minlength=n)
                num_cols = max(self.col_filt.sum(), n)
                exp_ct = np.bincount(np.arange(num_cols) % n, minlength=n)
                if (col_idx_ct > exp_ct).any():
                    warnings.warn("Some of your columns never make an appearance in the animation. "
                                    "To reduce color repetition, set `filter_column_colors` to `True`")
        return bar_colors

    def set_xy_limits(self):
        limit = (.2, self.n_bars + .8)
        min_val = 1 if self.scale == 'log' else 0
        self.xlimit, self.ylimit = None, None
        if self.orientation == 'h':
            self.ylimit = limit
            if self.fixed_max:
                self.xlimit = [min_val, self.df_values.max().max() * 1.05 * 1.11]
        else:
            self.xlimit = limit
            if self.fixed_max:
                self.ylimit = [min_val, self.df_values.max().max() * 1.05 * 1.16]
  
    def get_frames(self):
        frames = []
        for i in range(len(self.df_values)):
            bar_loc = self.df_ranks.iloc[i].values
            top_filt = (bar_loc > 0) & (bar_loc < self.n_bars + 1)
            bar_vals = self.df_values.iloc[i].values[top_filt]
            bar_loc = bar_loc[top_filt]
            bar_loc = bar_loc + np.random.rand(len(bar_loc)) / 10_000 # done to prevent stacking of bars
            x, y = (bar_vals, bar_loc) if self.orientation == 'h' else (bar_loc, bar_vals)
            
            cols = self.df_values.columns[top_filt]
            colors = self.bar_colors[top_filt]
            limit = self.ylimit if self.orientation == 'h' else self.xlimit
            label_axis = dict(tickmode='array', tickvals=bar_loc, ticktext=cols, range=limit)
            texttemplate = '%{x:,.0f}' if self.orientation == 'h' else '%{y:,.0f}'
            bar = go.Bar(x=x, y=y, width=self.bar_size, textposition=self.label_bars,
                         texttemplate=texttemplate, orientation=self.orientation, 
                         marker_color=colors)

            data = [bar]
            if self.perpendicular_bar_func:
                pbar = self.get_perpendicular_bar(bar_vals, i)
                data = [pbar, bar]

            if self.orientation == 'h':
                xaxis = dict(range=self.xlimit)
                yaxis = label_axis
            else:
                xaxis = label_axis
                yaxis = dict(range=self.ylimit)

            annotations = self.get_annotations(i)
            layout = go.Layout(xaxis=xaxis, yaxis=yaxis, annotations=annotations, showlegend=False)
            frames.append(go.Frame(data=data, layout=layout))
        return frames
    
    def get_annotations(self, i):
        annotations = []
        if self.period_label:
            if self.period_fmt:
                idx_val = self.df_values.index[i]
                if self.df_values.index.dtype.kind == 'M':
                    s = idx_val.strftime(self.period_fmt)
                else:
                    s = self.period_fmt.format(x=idx_val)
            else:
                s = self.str_index[i]
            x, y = self.period_label['x'], self.period_label['y']
            annotations.append(dict(text=s, x=x, y=y, xref="paper", yref="paper", 
                                    showarrow=False, font=dict(size=18)))

        if self.period_summary_func:
            values = self.df_values.iloc[i]
            ranks = self.df_ranks.iloc[i]
            text_dict = self.period_summary_func(values, ranks)
            if 'x' not in text_dict or 'y' not in text_dict or 's' not in text_dict:
                name = self.period_summary_func.__name__
                raise ValueError(f'The dictionary returned from `{name}` must contain '
                                  '"x", "y", and "s"')
            s, x, y = text_dict['s'], text_dict['x'], text_dict['y']
            annotations.append(dict(text=s, x=x, y=y, font=dict(size=14), 
                                    xref="paper", yref="paper", showarrow=False))

        return annotations

    def get_perpendicular_bar(self, bar_vals, i):
        if isinstance(self.perpendicular_bar_func, str):
            val = pd.Series(bar_vals).agg(self.perpendicular_bar_func)
        else:
            values = self.df_values.iloc[i]
            ranks = self.df_ranks.iloc[i]
            val = self.perpendicular_bar_func(values, ranks)

        vals = [val, val]
        if self.orientation == 'h':
            x, y, o = vals, self.ylimit, 'v'
            width = (self.xlimit[1] - self.xlimit[0]) * .02 
        else:
            x, y, o = self.xlimit, vals, 'h'
            width = (self.ylimit[1] - self.ylimit[0]) * .02 
        
        return go.Bar(x=x, y=y, width=width, orientation=o, marker_color='rgba(50, 50, 50, .2)')
            
    def make_animation(self):
        interval = self.period_length / self.steps_per_period
        frames = self.get_frames()
        data = frames[0].data
        layout = frames[0].layout
        layout.title = "Bar Chart Race"
        layout.updatemenus = [dict(
            type="buttons",
            buttons=[dict(label="Play",
                          method="animate",
                          args=[None, {"frame": {"duration": 10, "redraw": True},
                                       "fromcurrent": True}]
                         )
                    ])]

        fig = go.Figure(data=data, layout=layout, frames=frames)
        return fig


def bar_chart_race_plotly(df, filename=None, orientation='h', sort='desc', n_bars=None, 
                   fixed_order=False, fixed_max=False, steps_per_period=10, 
                   period_length=500, interpolate_period=False, label_bars=True, 
                   bar_size=.95, period_label=True, period_fmt=None, 
                   period_summary_func=None, perpendicular_bar_func=None, figsize=(6, 3.5),
                   cmap=None, title=None, title_size=None, bar_label_size=7, 
                   tick_label_size=7, shared_fontdict=None, scale='linear', 
                   fig=None, dpi=144, bar_kwargs=None, filter_column_colors=False):
    '''
    Create an animated bar chart race using Plotly. Data must be in 
    'wide' format where each row represents a single time period and each 
    column represents a distinct category. Optionally, the index can label 
    the time period.

    Bar height and location change linearly from one time period to the next.

    If no `filename` is given, an HTML string is returned, otherwise the 
    animation is saved to disk.

    You must have ffmpeg installed on your machine to save files to disk.
    Get ffmpeg here: https://www.ffmpeg.org/download.html

    To save .gif files you'll need to install ImageMagick.

    This is resource intensive - Start with just a few rows of data to test.


    Parameters
    ----------
    df : pandas DataFrame
        Must be a 'wide' DataFrame where each row represents a single period 
        of time. Each column contains the values of the bars for that 
        category. Optionally, use the index to label each time period.
        The index can be of any type.

    filename : `None` or str, default None
        If `None` return animation as an HTML5 string.
        If a string, save animation to that filename location. 
        Use .mp4, .gif, .html, .mpeg, .mov and any other extensions supported
        by ffmpeg or ImageMagick.

    orientation : 'h' or 'v', default 'h'
        Bar orientation - horizontal or vertical

    sort : 'desc' or 'asc', default 'desc'
        Choose how to sort the bars. Use 'desc' to put largest bars on top 
        and 'asc' to place largest bars on bottom.

    n_bars : int, default None
        Choose the maximum number of bars to display on the graph. 
        By default, use all bars. New bars entering the race will appear 
        from the edge of the axes.

    fixed_order : bool or list, default False
        When `False`, bar order changes every time period to correspond 
        with `sort`. When `True`, bars remained fixed according to their 
        final value corresponding with `sort`. Otherwise, provide a list 
        of the exact order of the categories for the entire duration.

    fixed_max : bool, default False
        Whether to fix the maximum value of the axis containing the values.
        When `False`, the axis for the values will have its maximum (xlim/ylim)
        just after the largest bar of the current time period. 
        The axis maximum will change along with the data.

        When True, the maximum axis value will remain constant for the 
        duration of the animation. For example, in a horizontal bar chart, 
        if the largest bar has a value of 100 for the first time period and 
        10,000 for the last time period. The xlim maximum will be 10,000 
        for each frame.

    steps_per_period : int, default 10
        The number of steps to go from one time period to the next. 
        The bars will grow linearly between each period.

    period_length : int, default 500
        Number of milliseconds to animate each period (row). 
        Default is 500ms (half of a second)

    interpolate_period : bool, default `False`
        Whether to interpolate the period. Only valid for datetime or
        numeric indexes. When set to `True`, for example, 
        the two consecutive periods 2020-03-29 and 2020-03-30 with 
        `steps_per_period` set to 4 would yield a new index of
        2020-03-29 00:00:00
        2020-03-29 06:00:00
        2020-03-29 12:00:00
        2020-03-29 18:00:00
        2020-03-30 00:00:00
    
    label_bars : 'inside' or 'outside', default `None`
        Whether to label the bars with their values on the inside or outside

    bar_size : float, default .95
        Height/width of bars for horizontal/vertical bar charts. 
        Use a number between 0 and 1
        Represents the fraction of space that each bar takes up. 
        When equal to 1, no gap remains between the bars.

    period_label : bool or dict, default `True`
        If `True` or dict, use the index as a large text label
        on the axes whose value changes

        Use a dictionary to supply the exact position of the period
        along with any valid parameters of the plotly `text` method.
        At a minimum, you must supply both 'x' and 'y' in axes coordinates

        Example:
        {
            'x': .99,
            'y': .8,
        }
        
        If `False` - don't place label on axes

        The default location depends on `orientation` and `sort`
        * h, desc -> x=.95, y=.15, ha='right', va='center'
        * h, asc -> x=.95, y=.85, ha='right', va='center'
        * v, desc -> x=.95, y=.85, ha='right', va='center'
        * v, asc -> x=.05, y=.85, ha='left', va='center'

    period_fmt : str, default `None`
        Either a string with date directives or 
        a new-style (Python 3.6+) formatted string

        For a string with a date directive, find the complete list here
        https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
        
        Example of string with date directives
            '%B %d, %Y'
        Will change 2020/03/29 to March 29, 2020
        
        For new-style formatted string. Use curly braces and the variable `x`, 
        which will be passed the current period's index value.
        Example:
            'Period {x:10.2f}'

        Date directives will only be used for datetime indexes.

    period_summary_func : function, default None
        Custom text added to the axes each period.
        Create a user-defined function that accepts two pandas Series of the 
        current time period's values and ranks. It must return a dictionary 
        containing at a minimum the keys "x", "y", and "s" which will be 
        passed to the plotly `text` method.

        Example:
        def func(values, ranks):
            total = values.sum()
            s = f'Worldwide deaths: {total}'
            return {'x': .85, 'y': .2, 's': s, 'size': 11}

    perpendicular_bar_func : function or str, default None
        Creates a single bar perpendicular to the main bars that spans the 
        length of the axis. 
        
        Use either a string that the DataFrame `agg` method understands or a 
        user-defined function.
            
        DataFrame strings - 'mean', 'median', 'max', 'min', etc..

        The function is passed two pandas Series of the current time period's
        data and ranks. It must return a single value.

        def func(values, ranks):
            return values.quantile(.75)

    figsize : two-item tuple of numbers, default (6, 3.5)
        matplotlib figure size in inches. Will be overridden if figure 
        supplied to `fig`.

    cmap : str, matplotlib colormap instance, or list of colors, default 'dark12'
        Colors to be used for the bars. All matplotlib and plotly colormaps are 
        available by string name. Colors will repeat if there are more bars than colors.

        "dark12" is a discrete colormap with every other color from the "dark24"
        plotly colormap. If there are more than 12 columns, then the default 
        colormap will be "dark24"

        Append "_r" to the colormap name to use the reverse of the colormap.
        i.e. "dark12_r"

    title : str, default None
        Title of plot

    title_size : number or str, default plt.rcParams['axes.titlesize']
        Size in points of title or relative size str. See Font Help below.

    bar_label_size : number or str, default 7
        Size in points or relative size str of numeric labels 
        just outside of the bars. See Font Help below.

    tick_label_size : number or str, default 7
        Size in points of tick labels. See Font Help below. 
        See Font Help below

    shared_fontdict : dict, default None
        Dictionary of font properties shared across the tick labels, 
        bar labels, period labels, and title. The only property not shared 
        is `size`. It will be ignored if you try to set it.

        Possible keys are:
            'family', 'weight', 'color', 'style', 'stretch', 'weight', 'variant'
        Here is an example dictionary:
        {
            'family' : 'Helvetica',
            'weight' : 'bold',
            'color' : 'rebeccapurple'
        }

    scale : 'linear' or 'log', default 'linear'
        Type of scaling to use for the axis containing the values

    fig : matplotlib Figure, default None
        For greater control over the aesthetics, supply your own figure.

    dpi : int, default 144
        Dots per Inch of the matplotlib figure

    bar_kwargs : dict, default `None` (alpha=.8)
        Other keyword arguments (within a dictionary) forwarded to the 
        matplotlib `barh`/`bar` function. If no value for 'alpha' is given,
        then it is set to .8 by default.
        Some examples:
            `ec` - edgecolor - color of edge of bar. Default is 'white'
            `lw` - width of edge in points. Default is 1.5
            `alpha` - opacity of bars, 0 to 1

    filter_column_colors : bool, default `False`
        When setting n_bars, it's possible that some columns never 
        appear in the animation. Regardless, all columns get assigned
        a color by default. 
        
        For instance, suppose you have 100 columns 
        in your DataFrame, set n_bars to 10, and 15 different columns 
        make at least one appearance in the animation. Even if your 
        colormap has at least 15 colors, it's possible that many 
        bars will be the same color, since each of the 100 columns is
        assigned of the colormaps colors.

        Setting this to `True` will map your colormap to just those 
        columns that make an appearance in the animation, helping
        avoid duplication of colors.

        Setting this to `True` will also have the (possibly unintended)
        consequence of changing the colors of each color every time a 
        new integer for n_bars is used.

        EXPERIMENTAL
        This parameter is experimental and may be changed/removed
        in a later version.


    Returns
    -------
    When `filename` is left as `None`, an HTML5 video is returned as a string.
    Otherwise, a file of the animation is saved and `None` is returned.

    Notes
    -----
    It is possible for some bars to be out of order momentarily during a 
    transition since both height and location change linearly and not 
    directly with respect to their current value. This keeps all the 
    transitions identical.

    Examples
    --------
    Use the `load_data` function to get an example dataset to 
    create an animation.

    df = bcr.load_dataset('covid19')
    bcr.bar_chart_race(
        df=df, 
        filename='covid19_horiz_desc.mp4', 
        orientation='h', 
        sort='desc', 
        n_bars=8, 
        fixed_order=False, 
        fixed_max=True, 
        steps_per_period=10, 
        period_length=500, 
        interpolate_period=False, 
        label_bars=True, 
        bar_size=.95, 
        period_label={'x': .99, 'y': .8, 'ha': 'right', 'va': 'center'}, 
        period_fmt='%B %d, %Y', 
        period_summary_func=lambda v, r: {'x': .85, 'y': .2, 
                                          's': f'Total deaths: {v.sum()}', 
                                          'ha': 'right', 'size': 11}, 
        perpendicular_bar_func='median', 
        figsize=(5, 3), 
        dpi=144,
        cmap='dark12', 
        title='COVID-19 Deaths by Country', 
        title_size='', 
        bar_label_size=7, 
        tick_label_size=7, 
        shared_fontdict={'family' : 'Helvetica', 'weight' : 'bold', 'color' : '.1'}, 
        scale='linear', 
        fig=None, 
        bar_kwargs={'alpha': .7},
        filter_column_colors=False)        

    Font Help
    ---------
    Font size can also be a string - 'xx-small', 'x-small', 'small',  
        'medium', 'large', 'x-large', 'xx-large', 'smaller', 'larger'
    These sizes are relative to plt.rcParams['font.size'].
    '''
    bcr = _BarChartRace(df, filename, orientation, sort, n_bars, fixed_order, fixed_max,
                        steps_per_period, period_length, interpolate_period, label_bars, bar_size, 
                        period_label, period_fmt, period_summary_func, perpendicular_bar_func, 
                        figsize, cmap, title, title_size, bar_label_size, tick_label_size, 
                        shared_fontdict, scale, fig, dpi, bar_kwargs, filter_column_colors)
    return bcr.make_animation()