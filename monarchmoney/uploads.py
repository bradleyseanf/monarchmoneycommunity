"""Uploads client operations."""

from .monarchmoney import (
    Any,
    BalanceHistoryRow,
    DEFAULT_DELAY_SECS,
    DEFAULT_TIMEOUT_SECS,
    Dict,
    FormData,
    List,
    MonarchMoneyEndpoints,
    RequestFailedException,
    asyncio,
    json,
    mimetypes,
    time,
    uuid,
)


def _query(operation: str):
    from .monarchmoney import _query as load_query

    return load_query(operation)


class UploadsMixin:

    async def upload_account_balance_history(
        self,
        account_id: str,
        csv_content: List[BalanceHistoryRow],
        timeout: int = DEFAULT_TIMEOUT_SECS,
        delay: int = DEFAULT_DELAY_SECS,
    ) -> bool:
        """
        Uploads the account balance history CSV for a specified account.

        :param account_id: The account ID to apply the history to.
        :param csv_content: CSV representation of the balance history.
                            Headers: Date, Amount, and Account Name.
        :param timeout: The number of seconds to wait before timing out
        :param delay: The number of seconds to wait for each check on whether parsing is completed
        """
        if not account_id or not csv_content:
            raise RequestFailedException("account_id and csv_content cannot be empty")

        csv_string = self._convert_to_csv_string(csv_content)

        filename = "upload.csv"
        form = FormData()
        form.add_field("files", csv_string, filename=filename, content_type="text/csv")
        form.add_field("account_files_mapping", json.dumps({filename: account_id}))

        upload_response = await self._upload_form_data(
            url=MonarchMoneyEndpoints.getAccountBalanceHistoryUploadEndpoint(),
            data=form,
        )

        session_key = upload_response["session_key"]

        parse_response = await self._initiate_upload_balance_history_session(
            session_key=session_key
        )

        is_completed = (
            parse_response["parseBalanceHistory"]["uploadBalanceHistorySession"][
                "status"
            ]
            == "completed"
        )

        start = time.time()
        while not is_completed and (time.time() <= (start + timeout)):
            await asyncio.sleep(delay)

            is_completed = (
                await self._is_upload_balance_history_complete(session_key)
            )["uploadBalanceHistorySession"]["status"] == "completed"

        return is_completed

    async def _initiate_upload_balance_history_session(self, session_key: str) -> dict:
        """
        Triggers parsing of the uploaded balance history CSV file.

        :param session_key: The session key for the uploaded file.
        """

        query = _query("uploads/_initiate_upload_balance_history_session")

        variables = {"input": {"sessionKey": session_key}}

        return await self.gql_call(
            "Web_ParseUploadBalanceHistorySession", query, variables
        )

    async def _is_upload_balance_history_complete(self, session_key: str):
        """
        Retrieves the status of the upload balance history session.

        :param session_key: The session key for the uploaded file.
        """

        query = _query("uploads/_is_upload_balance_history_complete")

        variables = {"sessionKey": session_key}

        return await self.gql_call(
            "Web_GetUploadBalanceHistorySession", query, variables
        )

    async def _get_transaction_attachment_upload_info(self, transaction_id: str):
        """
        Retrieves the request parameters to upload the transaction attachment
        :param transaction_id: The selected transaction id to get the request parameters for
        """

        query = _query("uploads/_get_transaction_attachment_upload_info")

        variables = {"transactionId": transaction_id}

        return await self.gql_call(
            operation="Common_GetTransactionAttachmentUploadInfo",
            variables=variables,
            graphql_query=query,
        )

    async def _create_retail_sync_session(self) -> Dict[str, Any]:
        """
        Creates a bulk retail sync session used to upload receipts to the inbox.
        """
        query = _query("uploads/_create_retail_sync_session")

        return await self.gql_call(
            operation="Common_CreateBulkRetailSync",
            variables={"input": {"count": 1}},
            graphql_query=query,
        )

    async def _start_retail_sync(self, sync_id: str) -> Dict[str, Any]:
        """
        Starts a retail sync session, triggering Monarch's AI to process uploaded receipts.

        :param sync_id: The retail sync session ID returned by _create_retail_sync_session.
        """
        query = _query("uploads/_start_retail_sync")

        return await self.gql_call(
            operation="Common_StartRetailSync",
            variables={"syncId": sync_id},
            graphql_query=query,
        )

    async def _add_transaction_attachment(
        self,
        transaction_id: str,
        filename: str,
        public_id: str,
        extension: str,
        size_bytes: int,
    ):
        """
        Adds the attachment to the transaction

        :param transaction_id: The selected transaction id to upload the attachment to.
        :param filename: The name of the file including the extension name
        :param public_id: the public id from request params
        :param extension: the filename extension from request params
        :param size_bytes: the size of the file from request params
        """

        query = _query("uploads/_add_transaction_attachment")

        variables = {
            "input": {
                "extension": extension,
                "transactionId": transaction_id,
                "filename": filename,
                "publicId": public_id,
                "sizeBytes": size_bytes,
            },
        }

        return await self.gql_call(
            operation="Common_AddTransactionAttachment",
            variables=variables,
            graphql_query=query,
        )

    async def upload_attachment(
        self,
        transaction_id: str,
        file_content: bytes,
        filename: str,
    ):
        """
        Uploads an attachment to a transaction

        :param transaction_id: The selected transaction id to upload the attachment to.
        :param file_content: The binary file content
        :param filename: The name of the file including the extension name
        """

        response = await self._get_transaction_attachment_upload_info(
            transaction_id=transaction_id
        )
        upload_request_params = response["getTransactionAttachmentUploadInfo"]["info"][
            "requestParams"
        ]

        mime_type, _ = mimetypes.guess_type(filename)
        mime_type = mime_type or "application/octet-stream"

        form = FormData()

        form.add_field("file", file_content, filename=filename, content_type=mime_type)
        form.add_field("timestamp", str(upload_request_params["timestamp"]))
        form.add_field("folder", upload_request_params["folder"])
        form.add_field("signature", upload_request_params["signature"])
        form.add_field("api_key", upload_request_params["api_key"])
        form.add_field("upload_preset", upload_request_params["upload_preset"])

        upload_response = await self._upload_form_data(
            url=MonarchMoneyEndpoints.getAttachmentUploadEndpoint(),
            data=form,
        )

        return await self._add_transaction_attachment(
            transaction_id=transaction_id,
            filename=filename,
            public_id=upload_response["public_id"],
            extension=upload_response["format"],
            size_bytes=upload_response["bytes"],
        )

    async def upload_receipt_to_inbox(
        self,
        file_content: bytes,
        filename: str,
    ) -> Dict[str, Any]:
        """
        Uploads a receipt to the Monarch general receipt inbox (not attached to a specific
        transaction), triggering Monarch's AI to categorize and match it automatically.

        :param file_content: The raw bytes of the receipt file.
        :param filename: The name of the file including its extension (e.g. "receipt.jpg").
        """
        result = await self._create_retail_sync_session()
        syncs = result.get("createBulkRetailSync", {}).get("retailSyncs", [])
        errors = result.get("createBulkRetailSync", {}).get("errors") or []
        if not syncs or errors:
            raise RequestFailedException(
                f"Failed to create retail sync session: {errors}"
            )
        sync_id = syncs[0]["id"]

        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        metadata = json.dumps(
            {
                "orderId": str(uuid.uuid4()),
                "vendor": "user_import",
                "payloadType": "order",
                "contentType": mime_type,
            }
        )

        form = FormData()
        form.add_field("payloads_count", "1")
        form.add_field("metadata_0", metadata)
        form.add_field(
            "payload_0", file_content, filename=filename, content_type=mime_type
        )

        await self._upload_form_data(
            url=MonarchMoneyEndpoints.getRetailSyncFilesEndpoint(sync_id),
            data=form,
        )

        result = await self._start_retail_sync(sync_id)
        start = result.get("startRetailSync") or {}
        errors = start.get("errors") or []
        if errors or not start.get("retailSync"):
            raise RequestFailedException(f"Failed to start retail sync: {errors}")
        return start["retailSync"]

    async def _initiate_upload_attachment_session(self, session_key: str) -> dict:
        """
        Triggers parsing of the uploaded balance history CSV file.

        :param session_key: The session key for the uploaded file.
        """

        query = _query("uploads/_initiate_upload_attachment_session")

        variables = {"input": {"sessionKey": session_key}}

        return await self.gql_call(
            "Web_ParseUploadBalanceHistorySession", query, variables
        )

    async def _is_upload_attachment_complete(self, session_key: str):
        """
        Retrieves the status of the upload balance history session.

        :param session_key: The session key for the uploaded file.
        """

        query = _query("uploads/_is_upload_attachment_complete")

        variables = {"sessionKey": session_key}

        return await self.gql_call(
            "Web_GetUploadBalanceHistorySession", query, variables
        )
