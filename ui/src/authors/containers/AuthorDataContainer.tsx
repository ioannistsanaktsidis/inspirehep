import React, { useEffect, useMemo } from 'react';
import { connect, RootStateOrAny } from 'react-redux';

import { Action, ActionCreator } from 'redux';
import SearchPageContainer from '../../data/containers/SearchPageContainer';
import { searchBaseQueriesUpdate } from '../../actions/search';
import { AUTHOR_DATA_NS } from '../../search/constants';

const AuthorData = ({
  authorFacetName,
  onBaseQueriesChange,
}: {
  authorFacetName: string;
  onBaseQueriesChange: (baseQueries: any) => void;
}) => {
  useEffect(() => {
    const baseQuery = {
      author: [authorFacetName],
    };
    if (baseQuery) {
      onBaseQueriesChange({
        baseQuery,
      });
    }
  }, [authorFacetName, onBaseQueriesChange]);

  return <SearchPageContainer />;
};

const stateToProps = (state: RootStateOrAny) => ({
  authorFacetName: state.authors.getIn([
    'data',
    'metadata',
    'facet_author_name',
  ]),
});

const dispatchToProps = (dispatch: ActionCreator<Action>) => ({
  onBaseQueriesChange(baseQueries: any) {
    dispatch(searchBaseQueriesUpdate(AUTHOR_DATA_NS, baseQueries));
  },
});

export default connect(stateToProps, dispatchToProps)(AuthorData);
