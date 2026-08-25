import { head, includes, trim, values } from "lodash";
import React from "react";
import PropTypes from "prop-types";

import LoadingState from "@/components/items-list/components/LoadingState";
import routeWithUserSession from "@/components/ApplicationArea/routeWithUserSession";
import navigateTo from "@/components/ApplicationArea/navigateTo";

import { currentUser } from "@/services/auth";
import notification from "@/services/notification";
import InsightService from "@/services/insight";
import { Query as QueryService } from "@/services/query";
import routes from "@/services/routes";

import MenuButton from "./components/MenuButton";
import InsightView from "./InsightView";
import InsightEdit from "./InsightEdit";
import InsightNew from "./InsightNew";

const MODES = {
  NEW: 0,
  VIEW: 1,
  EDIT: 2,
};

export function getDefaultName(insight) {
  return trim(insight && insight.name) || "New Insight";
}

class Insight extends React.Component {
  static propTypes = {
    mode: PropTypes.oneOf(values(MODES)),
    insightId: PropTypes.string,
    onError: PropTypes.func,
  };

  static defaultProps = {
    mode: null,
    insightId: null,
    onError: () => {},
  };

  _isMounted = false;

  state = {
    insight: null,
    queryResult: null,
    isLoadingQueryResult: false,
    queryResultError: null,
    canEdit: false,
    mode: null,
  };

  componentDidMount() {
    this._isMounted = true;
    const { mode } = this.props;
    this.setState({ mode });

    if (mode === MODES.NEW) {
      this.setState({
        insight: {
          name: "",
          analysis_perspective: "",
          options: {
            dimension_column: null,
            category_column: null,
            message_to_column: null,
          },
        },
        canEdit: true,
      });
    } else {
      const { insightId } = this.props;
      InsightService.get({ id: insightId })
        .then(insight => {
          if (this._isMounted) {
            const canEdit = currentUser.canEdit(insight);

            if (!canEdit) {
              this.setState({ mode: MODES.VIEW });
              notification.warn(
                "You cannot edit this insight",
                "You do not have sufficient permissions to edit this insight, and have been redirected to the view-only page.",
                { duration: 0 }
              );
            }

            this.setState({ insight, canEdit });
            this.onQuerySelected(insight.query);
          }
        })
        .catch(error => {
          if (this._isMounted) {
            this.props.onError(error);
          }
        });
    }
  }

  componentWillUnmount() {
    this._isMounted = false;
  }

  save = () => {
    const { insight } = this.state;
    const name = trim(insight.name);
    const perspective = trim(insight.analysis_perspective || "");

    if (!name) {
      notification.error("Please enter an Insight name.");
      return Promise.reject(new Error("name required"));
    }
    if (!perspective) {
      notification.error("Please enter an analysis perspective.");
      return Promise.reject(new Error("analysis_perspective required"));
    }

    insight.name = name;
    insight.analysis_perspective = perspective;

    return InsightService.save(insight)
      .then(saved => {
        notification.success("Saved.");
        navigateTo(`insights/${saved.id}`, true);
        this.setState({ insight: saved, mode: MODES.VIEW });
      })
      .catch(() => {
        notification.error("Failed saving insight.");
      });
  };

  onQuerySelected = query => {
    if (!query) {
      this.setState(({ insight }) => ({
        insight: Object.assign(insight, { query: null }),
        queryResult: null,
        isLoadingQueryResult: false,
        queryResultError: null,
      }));
      return;
    }

    this.setState(({ insight }) => ({
      insight: Object.assign(insight, { query }),
      queryResult: null,
      isLoadingQueryResult: true,
      queryResultError: null,
    }));

    // Selector の簡易オブジェクトではなく、最新のクエリ定義とキャッシュ結果を取得する
    QueryService.get({ id: query.id })
      .then(fullQuery => {
        if (!this._isMounted) {
          return null;
        }

        this.setState(({ insight }) => ({
          insight: Object.assign(insight, { query: fullQuery }),
        }));

        if (!fullQuery.latest_query_data_id && !fullQuery.latest_query_data) {
          const message = "This query has no cached results. Run the query once, then select it again.";
          notification.warn("No cached query result", message);
          this.setState({
            isLoadingQueryResult: false,
            queryResultError: message,
          });
          return null;
        }

        return new QueryService(fullQuery).getQueryResultPromise();
      })
      .then(queryResult => {
        if (!this._isMounted || !queryResult) {
          return;
        }

        const columns = queryResult.getColumnNames();
        const options = { ...(this.state.insight.options || {}) };
        ["dimension_column", "category_column", "message_to_column"].forEach(key => {
          if (key === "message_to_column") {
            if (options[key] && !includes(columns, options[key])) {
              options[key] = null;
            }
            return;
          }
          if (!options[key] || !includes(columns, options[key])) {
            options[key] = head(columns);
          }
        });

        this.setState(({ insight }) => ({
          queryResult,
          isLoadingQueryResult: false,
          queryResultError: null,
          insight: Object.assign(insight, { options: { ...insight.options, ...options } }),
        }));
      })
      .catch(error => {
        if (!this._isMounted) {
          return;
        }
        const message = (error && error.message) || "Failed to load query data.";
        notification.error("Failed loading query data", message);
        this.setState({
          isLoadingQueryResult: false,
          queryResultError: message,
        });
      });
  };

  onNameChange = name => {
    const { insight } = this.state;
    this.setState({
      insight: Object.assign(insight, { name }),
    });
  };

  onPerspectiveChange = analysis_perspective => {
    const { insight } = this.state;
    this.setState({
      insight: Object.assign(insight, { analysis_perspective }),
    });
  };

  setInsightOptions = obj => {
    const { insight } = this.state;
    const options = { ...insight.options, ...obj };
    this.setState({
      insight: Object.assign(insight, { options }),
    });
  };

  delete = () => {
    const { insight } = this.state;
    return InsightService.delete(insight)
      .then(() => {
        notification.success("Insight deleted successfully.");
        navigateTo("insights");
      })
      .catch(() => {
        notification.error("Failed deleting insight.");
      });
  };

  evaluate = () => {
    const { insight } = this.state;
    return InsightService.evaluate(insight)
      .then(() => {
        notification.success("Insight evaluation queued. Refresh page for updated results.");
      })
      .catch(() => {
        notification.error("Failed to evaluate insight.");
      });
  };

  edit = () => {
    const { id } = this.state.insight;
    navigateTo(`insights/${id}/edit`, true);
    this.setState({ mode: MODES.EDIT });
  };

  cancel = () => {
    const { id } = this.state.insight;
    navigateTo(`insights/${id}`, true);
    this.setState({ mode: MODES.VIEW });
  };

  render() {
    const { insight } = this.state;
    if (!insight) {
      return <LoadingState className="m-t-30" />;
    }

    const { queryResult, isLoadingQueryResult, queryResultError, mode, canEdit } = this.state;

    const menuButton = <MenuButton doDelete={this.delete} canEdit={canEdit} evaluate={this.evaluate} />;

    const commonProps = {
      insight,
      queryResult,
      isLoadingQueryResult,
      queryResultError,
      save: this.save,
      menuButton,
      onQuerySelected: this.onQuerySelected,
      onNameChange: this.onNameChange,
      onPerspectiveChange: this.onPerspectiveChange,
      onColumnsChange: this.setInsightOptions,
    };

    return (
      <div className="alert-page">
        <div className="container">
          {mode === MODES.NEW && <InsightNew {...commonProps} />}
          {mode === MODES.VIEW && <InsightView canEdit={canEdit} onEdit={this.edit} {...commonProps} />}
          {mode === MODES.EDIT && <InsightEdit cancel={this.cancel} {...commonProps} />}
        </div>
      </div>
    );
  }
}

routes.register(
  "Insights.New",
  routeWithUserSession({
    path: "/insights/new",
    title: "New Insight",
    render: pageProps => <Insight {...pageProps} mode={MODES.NEW} />,
  })
);
routes.register(
  "Insights.View",
  routeWithUserSession({
    path: "/insights/:insightId",
    title: "Insight",
    render: pageProps => <Insight {...pageProps} mode={MODES.VIEW} />,
  })
);
routes.register(
  "Insights.Edit",
  routeWithUserSession({
    path: "/insights/:insightId/edit",
    title: "Insight",
    render: pageProps => <Insight {...pageProps} mode={MODES.EDIT} />,
  })
);
