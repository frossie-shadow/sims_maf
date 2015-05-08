import os
import numpy as np
import matplotlib.pyplot as plt
import lsst.sims.maf.utils as utils

__all__ = ['PlotHandler', 'BasePlotter']

class BasePlotter(object):
    """
    Serve as the base type for MAF plotters and example of API.
    """
    def __init__(self):
        self.plotType = None
        self.defaultPlotDict = None
    def __call__(self, metricValue, slicer, userPlotDict, fignum=None):
        pass


class PlotHandler(object):

    def __init__(self, outDir='.', resultsDb=None, savefig=True,
                 figformat='pdf', dpi=600, thumbnail=True):
        self.outDir = outDir
        self.resultsDb = resultsDb
        self.savefig = savefig
        self.figformat = figformat
        self.dpi = dpi
        self.thumbnail = thumbnail
        self.filtercolors = {'u':'b', 'g':'g', 'r':'y',
                             'i':'r', 'z':'m', 'y':'k'}
        self.filterorder = {'u':0, 'g':1, 'r':2, 'i':3, 'z':4, 'y':5}

    def setMetricBundles(self, mBundles):
        """
        Set the metric bundle or bundles (list or dictionary).
        Reuse the PlotHandler by resetting this reference.
        The metric bundles have to have the same slicer.
        """
        self.mBundles = []
        self.plotDict = {}
        # Try to add the metricBundles in filter order.
        if isinstance(mBundles, dict):
            for mB in mBundles.itervalues():
                vals = mB.fileRoot.split('_')
                forder = [self.filterorder.get(f, None) for f in vals if len(f) == 1]
                forder = [o for o in forder if o is not None]
                if len(forder) == 0:
                    forder = len(self.mBundles)
                else:
                    forder = forder[-1]
                self.mBundles.insert(forder, mB)
            self.slicer = self.mBundles[0].slicer
        else:
            for mB in mBundles:
                vals = mB.fileRoot.split('_')
                forder = [self.filterorder.get(f, None) for f in vals if len(f) == 1]
                forder = [o for o in forder if o is not None]
                if len(forder) == 0:
                    forder = len(self.mBundles)
                else:
                    forder = forder[-1]
                self.mBundles.insert(forder, mB)
            self.slicer = self.mBundles[0].slicer
        for mB in self.mBundles:
            if mB.slicer.slicerName != self.slicer.slicerName:
                raise ValueError('MetricBundle items must have the same type of slicer')
        self._combineMetricNames()
        self._combineRunNames()
        self._combineMetadata()
        self._combineSql()
        self.setPlotDict(reset=True)

    def setPlotDict(self, plotDict=None, plotFunc=None, reset=False):
        """
        Set or update (or 'reset') the plotDict for the (possibly joint) plots.
        """
        if reset:
            tmpPlotDict = {}
        else:
            tmpPlotDict = self.plotDict
        tmpPlotDict['title'] = self._buildTitle()
        tmpPlotDict['labels'] = self._buildLegendLabels()
        tmpPlotDict['colors'] = self._buildColors()
        tmpPlotDict['legendloc'] = 'upper right'
        tmpPlotDict['cbarFormat'] = self._buildCbarFormat()
        # Reset plotDict items set explicitly by plotter.
        if plotFunc is not None:
            tmpPlotDict['xlabel'], tmpPlotDict['ylabel'] = self._buildXYlabels(plotFunc)
            # Replace auto-generated plot dict items with things
            #  set by the plotterDefaults, if they are not None.
            plotterDefaults = plotFunc.defaultPlotDict
            for k, v in plotterDefaults.iteritems():
                if v is not None:
                    tmpPlotDict[k] = v
        # But replace anything set explicitly by the user in plotDict.
        if plotDict is not None:
            tmpPlotDict.update(plotDict)
        self.plotDict = tmpPlotDict

    def _combineMetricNames(self):
        """
        Combine metric names.
        """
        # Find the unique metric names.
        self.metricNames = set()
        for mB in self.mBundles:
            self.metricNames.add(mB.metric.name)
        # Find a pleasing combination of the metric names.
        order = ['u', 'g', 'r', 'i', 'z', 'y']
        if len(self.metricNames) == 1:
            jointName = ' '.join(self.metricNames)
        else:
            # Split each unique name into a list to see if we can merge the names.
            nameLengths = [len(x.split()) for x in self.metricNames]
            nameLists = [x.split() for x in self.metricNames]
            # If the metric names are all the same length, see if we can combine any parts.
            if len(set(nameLengths)) == 1:
                jointName = []
                for i in range(nameLengths[0]):
                    tmp = set([x[i] for x in nameLists])
                    # Try to catch special case of filters and put them in order.
                    if tmp.intersection(order) == tmp:
                        filterlist = ''
                        for f in order:
                            if f in tmp:
                                filterlist += f
                        jointName.append(filterlist)
                    else:
                        # Otherwise, just join and put into jointName.
                        jointName.append(''.join(tmp))
                jointName = ' '.join(jointName)
            # If the metric names are not the same length, just join everything.
            else:
                jointName = ' '.join(self.metricNames)
        self.jointMetricNames = jointName

    def _combineRunNames(self):
        """
        Combine runNames.
        """
        self.runNames = set()
        for mB in self.mBundles:
            self.runNames.add(mB.runName)
        self.jointRunNames = ' '.join(self.runNames)

    def _combineMetadata(self):
        """
        Combine metadata.
        """
        metadata = set()
        for mB in self.mBundles:
            metadata.add(mB.metadata)
        self.metadata = metadata
        # Find a pleasing combination of the metadata.
        if len(metadata) == 1:
            self.jointMetadata = ' '.join(metadata)
        else:
            order = ['u', 'g', 'r', 'i', 'z', 'y']
            # See if there are any subcomponents we can combine,
            # splitting on some values we expect to separate metadata clauses.
            splitmetas = []
            for m in self.metadata:
                # Try to split metadata into separate phrases (filter / proposal / constraint..).
                if ' and ' in m:
                    m = m.split(' and ')
                elif ', ' in m:
                    m = m.split(', ')
                else:
                    m = [m,]
                # Strip white spaces from individual elements.
                m = set([im.strip() for im in m])
                splitmetas.append(m)
            # Look for common elements and separate from the general metadata.
            common = set.intersection(*splitmetas)
            diff = [x.difference(common) for x in splitmetas]
            # Now look within the 'diff' elements and see if there are any common words to split off.
            diffsplit = []
            for d in diff:
                if len(d) >0:
                    m = set([x.split() for x in d][0])
                else:
                    m = set()
                diffsplit.append(m)
            diffcommon = set.intersection(*diffsplit)
            diffdiff = [x.difference(diffcommon) for x in diffsplit]
            # If the length of any of the 'differences' is 0, then we should stop and not try to subdivide.
            lengths = [len(x) for x in diffdiff]
            if min(lengths) == 0:
                # Sort them in order of length (so it goes 'g', 'g dithered', etc.)
                tmp = []
                for d in diff:
                    tmp.append(list(d)[0])
                diff = tmp
                xlengths = [len(x) for x in diff]
                idx = np.argsort(xlengths)
                diffdiff = [diff[i] for i in idx]
                diffcommon = []
            else:
                # diffdiff is the part where we might expect our filter values to appear; try to put this in order.
                diffdiffOrdered = []
                diffdiffEnd = []
                for f in order:
                    for d in diffdiff:
                        if len(d) == 1:
                            if list(d)[0] == f:
                                diffdiffOrdered.append(d)
                for d in diffdiff:
                    if d not in diffdiffOrdered:
                        diffdiffEnd.append(d)
                diffdiff = diffdiffOrdered + diffdiffEnd
                diffdiff = [' '.join(c) for c in diffdiff]
            # And put it all back together.
            combo = ', '.join([''.join(c) for c in diffdiff]) + ' ' + ' '.join([''.join(d) for d in diffcommon]) + ' '\
                    + ' '.join([''.join(e) for e in common])
            self.jointMetadata = combo

    def _combineSql(self):
        """
        Combine the sql constraints.
        """
        sqlconstraints = set()
        for mB in self.mBundles:
            sqlconstraints.add(mB.sqlconstraint)
        self.sqlconstraints = '; '.join(sqlconstraints)

    def _buildTitle(self):
        """
        Build a plot title from the metric names, runNames and metadata.
        """
        # Create a plot title from the unique parts of the metric/runName/metadata.
        if len(self.runNames) == 1:
            plotTitle = list(self.runNames)[0]
        if len(self.metadata) == 1:
            plotTitle += ' ' + list(self.metadata)[0]
        if len(self.metricNames) == 1:
            plotTitle += ': ' + list(self.metricNames)[0]
        if plotTitle == '':
            # If there were more than one of everything above, use joint metadata and metricNames.
            plotTitle = self.jointMetadata + ' ' + self.jointMetricNames
        return plotTitle

    def _buildXYlabels(self, plotFunc):
        """
        Build a plot x and y label.
        """
        if plotFunc.plotType == 'BinnedData':
            if len(self.mBundles) == 1:
                mB = self.mBundles[0]
                xlabel = mB.slicer.sliceColName + ' (' + mB.slicer.sliceColUnits + ')'
                ylabel = mB.metric.name + ' (' + mB.metric.units + ')'
            else:
                xlabel = set()
                for mB in self.mBundles:
                    xlabel.add(mB.slicer.sliceColName)
                xlabel = ', '.join(xlabel)
                ylabel = self.jointMetricNames
        else:
            if len(self.mBundles) == 1:
                mB = self.mBundles[0]
                xlabel = mB.metric.name
                if mB.metric.units is not None:
                    if len(mB.metric.units)>0:
                        xlabel +=  ' (' + mB.metric.units + ')'
                ylabel = None
            else:
                xlabel = self.jointMetricNames
                ylabel = set()
                for mB in self.mBundles:
                    if 'ylabel' in mB.plotDict:
                        ylabel.add(mB.plotDict['ylabel'])
                if len(ylabel) == 1:
                    ylabel = list(ylabel)[0]
                else:
                    ylabel = None
        return xlabel, ylabel

    def _buildLegendLabels(self):
        """
        Build a set of legend labels, using parts of the runName/metadata/metricNames that change.
        """
        if len(self.mBundles) == 1:
            return [None]
        labels = []
        for mB in self.mBundles:
            if 'label' in mB.plotDict:
                label = mB.plotDict['label']
            else:
                label = ''
                if len(self.runNames) > 1:
                    label += mB.runName
                if len(self.metadata) > 1:
                    label += ' ' + mB.metadata
                if len(self.metricNames) > 1:
                    label += ' ' + mB.metric.name
            labels.append(label)
        return labels

    def _buildColors(self):
        """
        Try to set an appropriate range of colors for the metric Bundles.
        """
        if len(self.mBundles) == 1:
            if 'color' in self.mBundles[0].plotDict:
                return [self.mBundles[0].plotDict['color']]
            else:
                return ['b']
        colors = []
        for mB in self.mBundles:
            if 'color' in mB.plotDict:
                color = mB.plotDict['color']
            else:
                if 'filter' in mB.sqlconstraint:
                    vals = mB.sqlconstraint.split('"')
                    for v in vals:
                        if len(v) == 1:
                            # Guess that this is the filter value
                            color = self.filtercolors[v]
                else:
                    color = 'b'
            colors.append(color)
        return colors

    def _buildCbarFormat(self):
        """
        Set the color bar format.
        """
        cbarFormat = None
        if len(self.mBundles) == 1:
            if self.mBundles[0].metric.metricDtype == 'int':
                cbarFormat = '%d'
        else:
            metricDtypes = set()
            for mB in self.mBundles:
                metricDtypes.add(mB.metric.metricDtype)
            if len(metricDtypes) == 1:
                if list(metricDtypes)[0] == 'int':
                    cbarFormat = '%d'
        return cbarFormat


    def _buildFileRoot(self, outfileSuffix=None):
        """
        Build a root filename for plot outputs.
        If there is only one metricBundle, this is equal to the metricBundle fileRoot + outfileSuffix.
        For multiple metricBundles, this is created from the runNames, metadata and metric names.
        """
        if len(self.mBundles) == 1:
            outfile = self.mBundles[0].fileRoot
        else:
            outfile = '_'.join([self.jointRunNames, self.jointMetricNames, self.jointMetadata])
            outfile += '_' + self.mBundles[0].slicer.slicerName[:4].upper()
        if outfileSuffix is not None:
            outfile += '_' + outfileSuffix
        outfile = utils.nameSanitize(outfile)
        return outfile

    def _buildDisplayDict(self):
        """
        Generate a display dictionary.
        This is most useful for when there are many metricBundles being combined into a single plot.
        """
        if len(self.mBundles) == 1:
            return self.mBundles[0].displayDict
        else:
            displayDict = {}
            group = set()
            subgroup = set()
            order = 0
            for mB in self.mBundles:
                group.add(mB.displayDict['group'])
                subgroup.add(mB.displayDict['subgroup'])
                if order < mB.displayDict['order']:
                    order = mB.displayDict['order'] + 1
            displayDict['order']  = order
            if len(group) > 1:
                displayDict['group'] = 'Comparisons'
            else:
                displayDict['group'] = list(group)[0]
            if len(subgroup) > 1:
                displayDict['subgroup'] = 'Comparisons'
            else:
                displayDict['subgroup'] = list(subgroup)[0]
            displayDict['caption'] = '%s metric(s) calculated on a %s grid, for opsim runs %s, for metadata values of %s.'\
              % (self.jointMetricNames, self.mBundles[0].slicer.slicerName, self.jointRunNames, self.jointMetadata)
            return displayDict

    def plot(self, plotFunc, plotDict=None, outfileSuffix=None):
        """
        Create plot for mBundles, using plotFunc.
        """
        if not plotFunc.objectPlotter:
            for mB in self.mBundles:
                if not mB.plotDict['metricIsColor']:
                    warnings.warn('Cannot plot object metric values with this plotter.')
                    return

        # Update x/y labels using plotType. User provided plotDict will override previous settings.
        self.setPlotDict(plotDict, plotFunc, reset=False)
        # Set outfile name.
        outfile = self._buildFileRoot(outfileSuffix)
        plotType = plotFunc.plotType
        # Make plot.
        fignum = None
        i = 0
        for mB in self.mBundles:
            self.plotDict['label'] = self.plotDict['labels'][i]
            self.plotDict['color'] = self.plotDict['colors'][i]
            fignum = plotFunc(mB.metricValues, mB.slicer, self.plotDict, fignum=fignum)
            i += 1
        if len(self.mBundles) > 1:
            plotType = 'Combo' + plotType
            plt.figure(fignum)
            plt.legend(loc=self.plotDict['legendloc'], fancybox=True, fontsize='smaller')
        # Save to disk and file info to resultsDb if desired.
        if self.savefig:
            fig = plt.figure(fignum)
            plotFile = outfile + '_' + plotType + '.' + self.figformat
            fig.savefig(os.path.join(self.outDir, plotFile), figformat=self.figformat, dpi=self.dpi)
            if self.thumbnail:
                thumbFile = 'thumb.' + outfile + '_' + plotType + '.png'
                plt.savefig(os.path.join(self.outDir, thumbFile), dpi=72)
            # Save information about the file to the resultsDb.
            if self.resultsDb:
                metricId = self.resultsDb.updateMetric(self.jointMetricNames, self.slicer.slicerName,
                                                       self.jointRunNames, self.sqlconstraints,
                                                       self.jointMetadata, None)
                # Add information to displays table (without overwriting previous information, if present).
                displayDict = self._buildDisplayDict()
                self.resultsDb.updateDisplay(metricId=metricId, displayDict=displayDict, overwrite=False)
                # Add plot information to plot table.
                self.resultsDb.updatePlot(metricId=metricId, plotType=plotType, plotFile=plotFile)
        return fignum
