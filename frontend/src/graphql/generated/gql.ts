/* eslint-disable */
import * as types from './graphql';
import type { TypedDocumentNode as DocumentNode } from '@graphql-typed-document-node/core';

/**
 * Map of all GraphQL operations in the project.
 *
 * This map has several performance disadvantages:
 * 1. It is not tree-shakeable, so it will include all operations in the project.
 * 2. It is not minifiable, so the string of a GraphQL query will be multiple times inside the bundle.
 * 3. It does not support dead code elimination, so it will add unused operations.
 *
 * Therefore it is highly recommended to use the babel or swc plugin for production.
 * Learn more about it here: https://the-guild.dev/graphql/codegen/plugins/presets/preset-client#reducing-bundle-size
 */
type Documents = {
    "\n  fragment OrderSummary on Order {\n    id\n    externalId\n    customer\n    amount\n    status\n    attempts\n    cycle\n    nextAttemptAt\n    lastError\n    internalReference\n    createdAt\n    updatedAt\n    finishedAt\n  }\n": typeof types.OrderSummaryFragmentDoc,
    "\n  fragment OrderHistory on Order {\n    history {\n      number\n      cycle\n      startedAt\n      finishedAt\n      durationMs\n      outcome\n      message\n    }\n  }\n": typeof types.OrderHistoryFragmentDoc,
    "\n  fragment OrderReprocesses on Order {\n    reprocesses {\n      number\n      cycle\n      requestedBy\n      reason\n      previousError\n      createdAt\n    }\n  }\n": typeof types.OrderReprocessesFragmentDoc,
    "\n  query Orders($status: OrderStatus, $search: String, $page: Int!, $size: Int!) {\n    orders(status: $status, search: $search, page: $page, size: $size) {\n      total\n      page\n      size\n      items {\n        ...OrderSummary\n      }\n    }\n  }\n": typeof types.OrdersDocument,
    "\n  query OrderStats {\n    orderStats {\n      received\n      processing\n      processed\n      failed\n      total\n    }\n  }\n": typeof types.OrderStatsDocument,
    "\n  query OrderDetail($id: ID!) {\n    order(id: $id) {\n      ...OrderSummary\n      ...OrderHistory\n      ...OrderReprocesses\n    }\n  }\n": typeof types.OrderDetailDocument,
    "\n  subscription OrdersUpdated {\n    orderUpdated {\n      ...OrderSummary\n    }\n  }\n": typeof types.OrdersUpdatedDocument,
    "\n  subscription OrderUpdated($id: ID!) {\n    orderUpdated(id: $id) {\n      ...OrderSummary\n      ...OrderHistory\n      ...OrderReprocesses\n    }\n  }\n": typeof types.OrderUpdatedDocument,
    "\n  query OrderSimulatorEnabled {\n    orderSimulatorEnabled\n  }\n": typeof types.OrderSimulatorEnabledDocument,
    "\n  mutation SimulateOrders($input: SimulateOrdersInput!) {\n    simulateOrders(input: $input) {\n      created\n      order {\n        ...OrderSummary\n      }\n    }\n  }\n": typeof types.SimulateOrdersDocument,
    "\n  mutation ResendOrder($id: ID!) {\n    resendOrder(id: $id) {\n      created\n      order {\n        ...OrderSummary\n      }\n    }\n  }\n": typeof types.ResendOrderDocument,
    "\n  mutation ReprocessOrder($id: ID!, $reason: String) {\n    reprocessOrder(id: $id, reason: $reason) {\n      ...OrderSummary\n      ...OrderHistory\n      ...OrderReprocesses\n    }\n  }\n": typeof types.ReprocessOrderDocument,
};
const documents: Documents = {
    "\n  fragment OrderSummary on Order {\n    id\n    externalId\n    customer\n    amount\n    status\n    attempts\n    cycle\n    nextAttemptAt\n    lastError\n    internalReference\n    createdAt\n    updatedAt\n    finishedAt\n  }\n": types.OrderSummaryFragmentDoc,
    "\n  fragment OrderHistory on Order {\n    history {\n      number\n      cycle\n      startedAt\n      finishedAt\n      durationMs\n      outcome\n      message\n    }\n  }\n": types.OrderHistoryFragmentDoc,
    "\n  fragment OrderReprocesses on Order {\n    reprocesses {\n      number\n      cycle\n      requestedBy\n      reason\n      previousError\n      createdAt\n    }\n  }\n": types.OrderReprocessesFragmentDoc,
    "\n  query Orders($status: OrderStatus, $search: String, $page: Int!, $size: Int!) {\n    orders(status: $status, search: $search, page: $page, size: $size) {\n      total\n      page\n      size\n      items {\n        ...OrderSummary\n      }\n    }\n  }\n": types.OrdersDocument,
    "\n  query OrderStats {\n    orderStats {\n      received\n      processing\n      processed\n      failed\n      total\n    }\n  }\n": types.OrderStatsDocument,
    "\n  query OrderDetail($id: ID!) {\n    order(id: $id) {\n      ...OrderSummary\n      ...OrderHistory\n      ...OrderReprocesses\n    }\n  }\n": types.OrderDetailDocument,
    "\n  subscription OrdersUpdated {\n    orderUpdated {\n      ...OrderSummary\n    }\n  }\n": types.OrdersUpdatedDocument,
    "\n  subscription OrderUpdated($id: ID!) {\n    orderUpdated(id: $id) {\n      ...OrderSummary\n      ...OrderHistory\n      ...OrderReprocesses\n    }\n  }\n": types.OrderUpdatedDocument,
    "\n  query OrderSimulatorEnabled {\n    orderSimulatorEnabled\n  }\n": types.OrderSimulatorEnabledDocument,
    "\n  mutation SimulateOrders($input: SimulateOrdersInput!) {\n    simulateOrders(input: $input) {\n      created\n      order {\n        ...OrderSummary\n      }\n    }\n  }\n": types.SimulateOrdersDocument,
    "\n  mutation ResendOrder($id: ID!) {\n    resendOrder(id: $id) {\n      created\n      order {\n        ...OrderSummary\n      }\n    }\n  }\n": types.ResendOrderDocument,
    "\n  mutation ReprocessOrder($id: ID!, $reason: String) {\n    reprocessOrder(id: $id, reason: $reason) {\n      ...OrderSummary\n      ...OrderHistory\n      ...OrderReprocesses\n    }\n  }\n": types.ReprocessOrderDocument,
};

/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 *
 *
 * @example
 * ```ts
 * const query = graphql(`query GetUser($id: ID!) { user(id: $id) { name } }`);
 * ```
 *
 * The query argument is unknown!
 * Please regenerate the types.
 */
export function graphql(source: string): unknown;

/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(source: "\n  fragment OrderSummary on Order {\n    id\n    externalId\n    customer\n    amount\n    status\n    attempts\n    cycle\n    nextAttemptAt\n    lastError\n    internalReference\n    createdAt\n    updatedAt\n    finishedAt\n  }\n"): (typeof documents)["\n  fragment OrderSummary on Order {\n    id\n    externalId\n    customer\n    amount\n    status\n    attempts\n    cycle\n    nextAttemptAt\n    lastError\n    internalReference\n    createdAt\n    updatedAt\n    finishedAt\n  }\n"];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(source: "\n  fragment OrderHistory on Order {\n    history {\n      number\n      cycle\n      startedAt\n      finishedAt\n      durationMs\n      outcome\n      message\n    }\n  }\n"): (typeof documents)["\n  fragment OrderHistory on Order {\n    history {\n      number\n      cycle\n      startedAt\n      finishedAt\n      durationMs\n      outcome\n      message\n    }\n  }\n"];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(source: "\n  fragment OrderReprocesses on Order {\n    reprocesses {\n      number\n      cycle\n      requestedBy\n      reason\n      previousError\n      createdAt\n    }\n  }\n"): (typeof documents)["\n  fragment OrderReprocesses on Order {\n    reprocesses {\n      number\n      cycle\n      requestedBy\n      reason\n      previousError\n      createdAt\n    }\n  }\n"];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(source: "\n  query Orders($status: OrderStatus, $search: String, $page: Int!, $size: Int!) {\n    orders(status: $status, search: $search, page: $page, size: $size) {\n      total\n      page\n      size\n      items {\n        ...OrderSummary\n      }\n    }\n  }\n"): (typeof documents)["\n  query Orders($status: OrderStatus, $search: String, $page: Int!, $size: Int!) {\n    orders(status: $status, search: $search, page: $page, size: $size) {\n      total\n      page\n      size\n      items {\n        ...OrderSummary\n      }\n    }\n  }\n"];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(source: "\n  query OrderStats {\n    orderStats {\n      received\n      processing\n      processed\n      failed\n      total\n    }\n  }\n"): (typeof documents)["\n  query OrderStats {\n    orderStats {\n      received\n      processing\n      processed\n      failed\n      total\n    }\n  }\n"];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(source: "\n  query OrderDetail($id: ID!) {\n    order(id: $id) {\n      ...OrderSummary\n      ...OrderHistory\n      ...OrderReprocesses\n    }\n  }\n"): (typeof documents)["\n  query OrderDetail($id: ID!) {\n    order(id: $id) {\n      ...OrderSummary\n      ...OrderHistory\n      ...OrderReprocesses\n    }\n  }\n"];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(source: "\n  subscription OrdersUpdated {\n    orderUpdated {\n      ...OrderSummary\n    }\n  }\n"): (typeof documents)["\n  subscription OrdersUpdated {\n    orderUpdated {\n      ...OrderSummary\n    }\n  }\n"];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(source: "\n  subscription OrderUpdated($id: ID!) {\n    orderUpdated(id: $id) {\n      ...OrderSummary\n      ...OrderHistory\n      ...OrderReprocesses\n    }\n  }\n"): (typeof documents)["\n  subscription OrderUpdated($id: ID!) {\n    orderUpdated(id: $id) {\n      ...OrderSummary\n      ...OrderHistory\n      ...OrderReprocesses\n    }\n  }\n"];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(source: "\n  query OrderSimulatorEnabled {\n    orderSimulatorEnabled\n  }\n"): (typeof documents)["\n  query OrderSimulatorEnabled {\n    orderSimulatorEnabled\n  }\n"];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(source: "\n  mutation SimulateOrders($input: SimulateOrdersInput!) {\n    simulateOrders(input: $input) {\n      created\n      order {\n        ...OrderSummary\n      }\n    }\n  }\n"): (typeof documents)["\n  mutation SimulateOrders($input: SimulateOrdersInput!) {\n    simulateOrders(input: $input) {\n      created\n      order {\n        ...OrderSummary\n      }\n    }\n  }\n"];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(source: "\n  mutation ResendOrder($id: ID!) {\n    resendOrder(id: $id) {\n      created\n      order {\n        ...OrderSummary\n      }\n    }\n  }\n"): (typeof documents)["\n  mutation ResendOrder($id: ID!) {\n    resendOrder(id: $id) {\n      created\n      order {\n        ...OrderSummary\n      }\n    }\n  }\n"];
/**
 * The graphql function is used to parse GraphQL queries into a document that can be used by GraphQL clients.
 */
export function graphql(source: "\n  mutation ReprocessOrder($id: ID!, $reason: String) {\n    reprocessOrder(id: $id, reason: $reason) {\n      ...OrderSummary\n      ...OrderHistory\n      ...OrderReprocesses\n    }\n  }\n"): (typeof documents)["\n  mutation ReprocessOrder($id: ID!, $reason: String) {\n    reprocessOrder(id: $id, reason: $reason) {\n      ...OrderSummary\n      ...OrderHistory\n      ...OrderReprocesses\n    }\n  }\n"];

export function graphql(source: string) {
  return (documents as any)[source] ?? {};
}

export type DocumentType<TDocumentNode extends DocumentNode<any, any>> = TDocumentNode extends DocumentNode<  infer TType,  any>  ? TType  : never;