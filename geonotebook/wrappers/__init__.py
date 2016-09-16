import os
import numpy as np
import pkg_resources as pr
import collections

class Band(object):
    def __init__(self, index, data):
        self.data = data
        self.index = index

    def __repr__(self):
        return "<{}('{}')>".format(self.__class__.__name__,
                                   self.name)

    def get_data(self, window=None, **kwargs):
        return self.reader.get_band_data(self.index,
                                         window=window,
                                         **kwargs)

    @property
    def min(self):
        return self.reader.get_band_min(self.index, masked=True)

    @property
    def max(self):
        return self.reader.get_band_max(self.index, masked=True)

    @property
    def mean(self):
        return self.reader.get_band_mean(self.index, masked=True)

    @property
    def stddev(self):
        return self.reader.get_band_stddev(self.index, masked=True)

    @property
    def name(self):
        return self.reader.get_band_name(self.index)

    @property
    def nodata(self):
        return self.reader.get_band_nodata(self.index)


    @property
    def reader(self):
        return self.data.reader


class RasterData(collections.Sequence):

    _concrete_data_types = {}
    band_class = Band

    @classmethod
    def register(cls, name, concrete_class):
        # TODO: some kind of validation on the API provided
        #       by the object from ep.load?
        cls._concrete_data_types[name] = concrete_class

    @classmethod
    def discover_concrete_types(cls):
        for ep in pr.iter_entry_points(group='geonotebook.wrappers.raster'):
            cls.register(ep.name, ep.load())

    @classmethod
    def is_valid(cls, path):
        try:
            f = open(path, "r")
        except OSError:
            return False
        finally:
            f.close()

        kind = os.path.splitext(path)[1][1:]

        return kind in cls._concrete_data_types.keys()


    def __init__(self, path, kind=None, indexes=None):
        if kind is None:
            # Get kind from the extension
            kind = os.path.splitext(path)[1][1:]

        try:
            self.reader = self._concrete_data_types[kind](path)
        except KeyError:
            raise NotImplementedError(
                "{} cannot parse files of type '{}'".format(
                    self.__class__.__name__, kind))

        self.band_indexes = range(1, self.reader.count + 1) \
            if indexes is None else indexes

        assert not min(self.band_indexes) < 1, \
            IndexError("Bands are indexed from 1")

        assert not max(self.band_indexes) > self.reader.count, \
            IndexError("Band index out of range")


    def index(self, *args, **kwargs):
        return self.reader.index(*args, **kwargs)

    def read(self, *args, **kwargs):
        return self.reader.read(*args, **kwargs)


    def get_data(self, window=None, masked=True, axis=2, **kwargs):
        if len(self) == 1:
            return self.band(self.band_indexes[0]).get_data(window=window,
                                                            masked=masked,
                                                            **kwargs)
        else:
            if masked:
                # TODO: fix masked array hack here
                kwargs["masked"] = False
                return np.ma.masked_values(
                    np.stack([self.band(i).get_data(window=window, **kwargs)
                              for i in self.band_indexes], axis=axis), self.band(1).nodata)
            else:
                return np.stack([self.band(i).get_data(window=window,
                                                       masked=masked,
                                                       **kwargs)
                                 for i in self.band_indexes], axis=axis)

    def __len__(self):
        return len(self.band_indexes)

    def __getitem__(self, key):
        if isinstance(key, slice):
            idx = key.indices(len(self.band_indexes))
            return RasterData(self.path, indexes=range(*idx))

        elif isinstance(key, (list, tuple)):
            return RasterData(self.path, indexes=key)

        else:
            return self.band(key)


    @property
    def min(self):
        return [self.band(i).min for i in self.band_indexes]

    @property
    def max(self):
        return [self.band(i).max for i in self.band_indexes]

    @property
    def mean(self):
        return [self.band(i).mean for i in self.band_indexes]

    @property
    def stddev(self):
        return [self.band(i).stddev for i in self.band_indexes]

    @property
    def nodata(self):
        return [self.band(i).nodata for i in self.band_indexes]

    def band(self, index):
        return self.band_class(index, self)

    @property
    def count(self):
        return self.reader.count

    @property
    def path(self):
        return self.reader.path



RasterData.discover_concrete_types()


class RasterDataCollection(collections.Sequence):
    def __init__(self, items, verify=True):
        if verify:
            assert all(RasterData.is_valid(i) for i in items), \
                TypeError("{} only takes a list of paths to supported raster data files"\
                          .format(self.__class__.__name__))

        self._cur = 0
        self._items = items

    def __iter__(self):
        for i in self._items:
            yield RasterData(i)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, key):
        if isinstance(key, slice):
            idx = key.indices(len(self._items))
            return RasterDataCollection([i for i in self._items if i in idx],
                                        verify=False)

        elif isinstance(key, (list, tuple)):
            return RasterDataCollection([p for i,p in enumerate(self._items) if i in key],
                                        verify=False)
        else:
            return RasterData(self._items[key])