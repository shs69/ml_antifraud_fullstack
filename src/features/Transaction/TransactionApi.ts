import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type { RootState } from "../../app/store";
import type {
  CreateTransactionBody,
  Transaction,
  Transactions,
} from "../../interfaces";
import { getRightNewTransaction } from "../../utils/utils";

export const transactionsApi = createApi({
  reducerPath: "transactionsApi",
  baseQuery: fetchBaseQuery({
    baseUrl: "http://localhost:8000/transactions",
    prepareHeaders: (headers, { getState }) => {
      const token = (getState() as RootState).login.token;
      if (token) headers.set("Authorization", `Bearer ${token}`);
      return headers;
    },
  }),
  tagTypes: ["Transaction"],
  endpoints: build => ({
    getTransactions: build.query<
      Transactions,
      { offset: number; limit: number }
    >({
      query: ({ offset, limit }) => ({
        url: `/?start=${offset.toString()}&limit=${limit.toString()}`,
        method: "GET",
      }),
      keepUnusedDataFor: 300,
      providesTags: [{ type: "Transaction", id: "LIST" }],
    }),
    createTransaction: build.mutation<Transaction, CreateTransactionBody>({
      query: transaction => {
        return {
          url: "/",
          method: "POST",
          body: getRightNewTransaction(transaction),
        };
      },
      invalidatesTags: [{ type: "Transaction", id: "LIST" }],
    }),
    uploadFile: build.mutation<Transactions, File>({
      query: file => {
        const formData = new FormData();
        formData.append("file", file);

        return {
          url: "/file",
          method: "POST",
          body: formData,
        };
      },
      invalidatesTags: [{ type: "Transaction", id: "LIST" }],
    }),
  }),
});

export const {
  useGetTransactionsQuery,
  useCreateTransactionMutation,
  useUploadFileMutation,
} = transactionsApi;
