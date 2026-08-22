import React from "react";
import routeWithUserSession from "@/components/ApplicationArea/routeWithUserSession";
import Link from "@/components/Link";
import PageHeader from "@/components/PageHeader";
import Paginator from "@/components/Paginator";
import EmptyState from "@/components/empty-state/EmptyState";
import { wrap as itemsList, ControllerType } from "@/components/items-list/ItemsList";
import { ResourceItemsSource } from "@/components/items-list/classes/ItemsSource";
import { StateStorage } from "@/components/items-list/classes/StateStorage";
import DynamicComponent from "@/components/DynamicComponent";

import ItemsTable, { Columns } from "@/components/items-list/components/ItemsTable";

import Insight from "@/services/insight";
import { currentUser } from "@/services/auth";
import routes from "@/services/routes";

class InsightsList extends React.Component {
  static propTypes = {
    controller: ControllerType.isRequired,
  };

  listColumns = [
    Columns.custom.sortable(
      (text, insight) => (
        <div>
          <Link className="table-main-title" href={"insights/" + insight.id}>
            {insight.name}
          </Link>
        </div>
      ),
      {
        title: "Name",
        field: "name",
      }
    ),
    Columns.custom((text, item) => item.user.name, { title: "Created By", width: "1%" }),
    Columns.custom(
      (text, insight) => insight.options && insight.options.dimension_column,
      { title: "Dimension", width: "1%", className: "text-nowrap" }
    ),
    Columns.custom(
      (text, insight) => insight.options && insight.options.category_column,
      { title: "Category", width: "1%", className: "text-nowrap" }
    ),
    Columns.timeAgo.sortable({ title: "Last Updated At", field: "updated_at", width: "1%" }),
    Columns.dateTime.sortable({ title: "Created At", field: "created_at", width: "1%" }),
  ];

  render() {
    const { controller } = this.props;

    return (
      <div className="page-insights-list">
        <div className="container">
          <PageHeader
            title={controller.params.pageTitle}
            actions={
              currentUser.hasPermission("list_insights") ? (
                <Link.Button block type="primary" href="insights/new">
                  <i className="fa fa-plus m-r-5" aria-hidden="true" />
                  New Insight
                </Link.Button>
              ) : null
            }
          />
          <div>
            {controller.isLoaded && controller.isEmpty ? (
              <DynamicComponent name="InsightsList.EmptyState">
                <EmptyState
                  icon="fa fa-lightbulb-o"
                  illustration="alert"
                  description="Detect anomalous changes in query results with AI"
                />
              </DynamicComponent>
            ) : (
              <div className="table-responsive bg-white tiled">
                <ItemsTable
                  loading={!controller.isLoaded}
                  items={controller.pageItems}
                  columns={this.listColumns}
                  orderByField={controller.orderByField}
                  orderByReverse={controller.orderByReverse}
                  toggleSorting={controller.toggleSorting}
                />
                <Paginator
                  showPageSizeSelect
                  totalCount={controller.totalItemsCount}
                  pageSize={controller.itemsPerPage}
                  onPageSizeChange={itemsPerPage => controller.updatePagination({ itemsPerPage })}
                  page={controller.page}
                  onChange={page => controller.updatePagination({ page })}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
}

const InsightsListPage = itemsList(
  InsightsList,
  () =>
    new ResourceItemsSource({
      isPlainList: true,
      getRequest() {
        return {};
      },
      getResource() {
        return Insight.query.bind(Insight);
      },
    }),
  () => new StateStorage({ orderByField: "created_at", orderByReverse: true, itemsPerPage: 20 })
);

routes.register(
  "Insights.List",
  routeWithUserSession({
    path: "/insights",
    title: "Insights",
    render: pageProps => <InsightsListPage {...pageProps} currentPage="insights" />,
  })
);
